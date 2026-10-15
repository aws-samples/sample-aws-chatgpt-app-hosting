import {
  AgentCoreApplication,
  AgentCoreMcp,
  AgentCorePaymentManager,
  AgentCorePaymentConnector,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
  type CustomJWTAuthorizerConfig,
  type HarnessDeploymentConfig,
} from '@aws/agentcore-cdk';
import { Annotations, CfnOutput, Duration, Fn, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { aws_bedrockagentcore as bedrockagentcore } from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Fixed resource names for the Coffee Discovery backend. These mirror the names
 * from the original hand-written CDK stack so the deployer scripts, README tool
 * prefixes, and OpenSearch index all keep working after the CLI migration.
 */
const COLLECTION_NAME = 'coffee-products';
const CART_TABLE_NAME = 'coffee-cart';
const RUNTIME_NAME = 'coffee_mcp';
const GATEWAY_NAME = 'coffee-runtime-noauth';
const GATEWAY_TARGET_NAME = 'coffee-runtime-direct';

/**
 * Harness deployment config: role-scoped fields (for IAM role + container build)
 * plus the full validated spec + its config directory so the L3 construct can
 * synthesize the AWS::BedrockAgentCore::Harness resource.
 */
export type HarnessConfig = HarnessDeploymentConfig;

export interface ManualPaymentConnectorSpec {
  name: string;
  provider: 'CoinbaseCDP' | 'StripePrivy';
  provisionMode?: 'MANUAL';
  credentialName: string;
  credentialProviderArn: string;
}

export interface QuickCreatePaymentConnectorSpec {
  name: string;
  provider: 'CoinbaseCDP';
  provisionMode: 'QUICK_CREATE';
  credentialName?: never;
  credentialProviderArn?: never;
}

export type PaymentConnectorSpec = ManualPaymentConnectorSpec | QuickCreatePaymentConnectorSpec;

export interface PaymentSpec {
  name: string;
  description?: string;
  authorizerType: 'AWS_IAM' | 'CUSTOM_JWT';
  authorizerConfiguration?: { customJWTAuthorizer: CustomJWTAuthorizerConfig };
  autoPayment?: boolean;
  paymentToolAllowlist?: string[];
  networkPreferences?: string[];
  connectors: PaymentConnectorSpec[];
}

export interface AgentCoreStackProps extends StackProps {
  /**
   * The AgentCore project specification containing agents, memories, and credentials.
   */
  spec: AgentCoreProjectSpec;
  /**
   * The MCP specification containing gateways and servers.
   */
  mcpSpec?: AgentCoreMcpSpec;
  /**
   * Credential provider ARNs from deployed state, keyed by credential name.
   */
  credentials?: Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;
  /**
   * Harness role configurations.
   */
  harnesses?: HarnessConfig[];
  /**
   * Parsed connectorParameters for non-S3 KB data sources, keyed by
   * connectorConfigFile path. Forwarded to AgentCoreApplication.
   */
  connectorParametersByFile?: Record<string, Record<string, unknown>>;
  /**
   * Payment specifications with resolved credential provider ARNs.
   */
  paymentSpec?: PaymentSpec[];
}

function toCdkId(name: string): string {
  return name.replace(/_/g, '');
}

/**
 * Decide whether a deployed runtime should receive payment env vars + IAM grants.
 * Payments today only ships a runtime shim for Python HTTP runtimes; injecting
 * AGENTCORE_PAYMENT_* env vars into TypeScript / MCP / A2A / AGUI runtimes
 * would surface env vars they cannot consume and would dilute least-privilege
 * IAM grants for runtimes that never call ProcessPayment.
 */
function isPaymentEligibleAgent(agent: { entrypoint?: string; protocol?: string }): boolean {
  if (agent.protocol && agent.protocol !== 'HTTP') {
    return false;
  }
  const entrypoint = typeof agent.entrypoint === 'string' ? agent.entrypoint : '';
  const entrypointFile = entrypoint.split(':')[0] ?? '';
  return entrypointFile.endsWith('.py');
}

/**
 * CDK Stack that deploys AgentCore infrastructure.
 *
 * This is a thin wrapper that instantiates L3 constructs.
 * All resource logic and outputs are contained within the L3 constructs.
 */
export class AgentCoreStack extends Stack {
  /** The AgentCore application containing all agent environments */
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);

    const { spec, mcpSpec, credentials, harnesses, connectorParametersByFile, paymentSpec } = props;

    // Create AgentCoreApplication with all agents and harness roles
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const appProps: Record<string, unknown> = { spec };
    if (harnesses?.length) {
      appProps.harnesses = harnesses;
    }
    if (connectorParametersByFile && Object.keys(connectorParametersByFile).length > 0) {
      appProps.connectorParametersByFile = connectorParametersByFile;
    }
    if (credentials) {
      appProps.credentials = credentials;
    }
    this.application = new AgentCoreApplication(this, 'Application', appProps as any);

    // Create AgentCoreMcp if there are gateways configured
    let mcp: AgentCoreMcp | undefined;
    if (mcpSpec?.agentCoreGateways && mcpSpec.agentCoreGateways.length > 0) {
      mcp = new AgentCoreMcp(this, 'Mcp', {
        projectName: spec.name,
        mcpSpec,
        agentCoreApplication: this.application,
        credentials,
        projectTags: spec.tags,
      });
    }

    // ================================================================
    // Coffee Discovery backend customizations
    //
    // The CLI/L3 constructs own the AgentCore Runtime and Gateway. Everything
    // below reproduces the resources that lived in the old hand-written CDK
    // stacks (infrastructure/stacks/agentcore_stack.py + image_hosting_stack.py)
    // minus the Cognito M2M pool and Docker bundling: DynamoDB cart, OpenSearch
    // Serverless collection + policies, S3 + CloudFront image hosting, runtime
    // env vars + IAM grants, and the hand-written gateway -> runtime target.
    // ================================================================
    this.addCoffeeDiscoveryBackend(mcp);

    // Payment infrastructure (no-op for this project) + stack-level output.
    this.addPaymentInfrastructure(spec, paymentSpec);
  }

  /**
   * Provision the Coffee Discovery data-plane resources and wire them to each
   * deployed runtime environment. Runs after `this.application` (and the MCP
   * gateway) are created so `env.runtime` and the gateway identifier are
   * available as CDK tokens.
   */
  private addCoffeeDiscoveryBackend(mcp?: AgentCoreMcp): void {
    // --------------------------------------------------------------
    // Resolve the runtime (by name) and gateway this backend wires itself to.
    //
    // The committed agentcore.json ships WITHOUT a runtime or gateway: the
    // reader adds them with `agentcore add agent` / `agentcore add gateway`
    // (README steps 2-3). Until both exist, there is nothing for the coffee
    // data layer to attach to, so skip the whole backend rather than throw —
    // throwing would break the reader's first `agentcore deploy --diff`, and
    // provisioning the OpenSearch collection with no runtime consuming it would
    // bill OCUs for nothing. Emit a visible CDK warning (surfaces in
    // `agentcore deploy`/`deploy --diff` synth output) telling the reader which
    // commands to run.
    // --------------------------------------------------------------
    const runtimeEnv = this.application.environments.get(RUNTIME_NAME);
    const gw = mcp?.gateways.get(GATEWAY_NAME);
    if (!runtimeEnv || !gw) {
      Annotations.of(this).addWarning(
        `Coffee Discovery backend skipped: no '${RUNTIME_NAME}' runtime and/or '${GATEWAY_NAME}' gateway in agentcore.json yet. ` +
          `Add them first:\n` +
          `  agentcore add agent --name ${RUNTIME_NAME} --type byo --language Python --protocol MCP --code-location ./mcp_server --entrypoint server.py\n` +
          `  agentcore add gateway --name ${GATEWAY_NAME} --protocol-type MCP --authorizer-type NONE\n` +
          `then re-run 'agentcore validate' and 'agentcore deploy'.`
      );
      return;
    }

    // --------------------------------------------------------------
    // DynamoDB cart table
    // --------------------------------------------------------------
    const cartTable = new dynamodb.Table(this, 'CoffeeCartTable', {
      tableName: CART_TABLE_NAME,
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // --------------------------------------------------------------
    // OpenSearch Serverless (VECTORSEARCH) collection + security policies
    // --------------------------------------------------------------
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'CollectionEncryptionPolicy', {
      name: 'coffee-products-enc',
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [{ ResourceType: 'collection', Resource: [`collection/${COLLECTION_NAME}`] }],
        AWSOwnedKey: true,
      }),
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'CollectionNetworkPolicy', {
      name: 'coffee-products-net',
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            { ResourceType: 'collection', Resource: [`collection/${COLLECTION_NAME}`] },
            { ResourceType: 'dashboard', Resource: [`collection/${COLLECTION_NAME}`] },
          ],
          AllowFromPublic: true,
        },
      ]),
    });

    const collection = new opensearchserverless.CfnCollection(this, 'CoffeeProductsCollection', {
      name: COLLECTION_NAME,
      type: 'VECTORSEARCH',
      description: 'Coffee product catalog with vector embeddings',
    });
    collection.addDependency(encryptionPolicy);
    collection.addDependency(networkPolicy);

    // --------------------------------------------------------------
    // S3 + CloudFront image hosting (folded in from ImageHostingStack)
    // --------------------------------------------------------------
    const bucket = new s3.Bucket(this, 'ProductImagesBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          exposedHeaders: ['ETag'],
          maxAge: 3600,
        },
      ],
      removalPolicy: RemovalPolicy.RETAIN, // Prevent accidental deletion of uploaded images
    });

    const oai = new cloudfront.OriginAccessIdentity(this, 'ProductImagesOAI', {
      comment: 'OAI for chatgpt-apps-aws bucket',
    });
    bucket.grantRead(oai);

    const responseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'ProductImagesResponseHeaders', {
      corsBehavior: {
        accessControlAllowCredentials: false,
        accessControlAllowOrigins: ['*'],
        accessControlAllowMethods: ['GET', 'HEAD'],
        accessControlAllowHeaders: ['*'],
        accessControlExposeHeaders: ['ETag'],
        accessControlMaxAge: Duration.hours(24),
        originOverride: true,
      },
      securityHeadersBehavior: {
        strictTransportSecurity: {
          accessControlMaxAge: Duration.days(365),
          includeSubdomains: true,
          override: true,
        },
      },
      customHeadersBehavior: {
        customHeaders: [{ header: 'Cache-Control', value: 'public, max-age=86400, immutable', override: true }],
      },
    });

    const distribution = new cloudfront.Distribution(this, 'ProductImagesCDN', {
      defaultBehavior: {
        // eslint-disable-next-line deprecation/deprecation
        origin: new origins.S3Origin(bucket, { originAccessIdentity: oai }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
        compress: true,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        responseHeadersPolicy,
      },
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      enableIpv6: true,
    });

    // --------------------------------------------------------------
    // Wire the backend into the deployed runtime environment
    //
    // The project declares exactly one runtime (coffee_mcp, resolved by name
    // above), so wire that single runtime rather than looping.
    // --------------------------------------------------------------
    const runtime = runtimeEnv.runtime;

    // Runtime env vars (dynamic CDK tokens — must be set here, not in
    // agentcore.json envVars, which only accepts static strings).
    runtime.addEnvironmentVariable('OPENSEARCH_ENDPOINT', collection.attrCollectionEndpoint);
    runtime.addEnvironmentVariable('CLOUDFRONT_DOMAIN', `https://${distribution.distributionDomainName}`);
    runtime.addEnvironmentVariable('CART_TABLE_NAME', cartTable.tableName);
    runtime.addEnvironmentVariable('AWS_REGION', this.region);
    // The gateway lists runtime tools as `<target>___<tool>`; the server echoes this prefix to the
    // widgets (structuredContent.tool_prefix) so their window.openai.callTool names match.

    // Runtime IAM grants.
    // bedrock:InvokeModel scoped to the single embedding model the server uses.
    // The CLI default runtime role may grant broader Bedrock access; this
    // explicit statement documents and pins the exact model dependency.
    runtime.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [`arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v1`],
      })
    );
    // aoss:APIAccessAll is the only data-plane IAM action OpenSearch Serverless
    // exposes; read/write authorization is enforced by the data access policy
    // below, which scopes this role to the coffee-products collection/index.
    runtime.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ['aoss:APIAccessAll'],
        resources: [collection.attrArn],
      })
    );
    runtime.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`,
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`,
        ],
      })
    );
    cartTable.grantReadWriteData(runtime.role);

    // --------------------------------------------------------------
    // OpenSearch data access policy (runtime roles + account root)
    //
    // The account root principal is intentional for this sample: it lets
    // whoever deploys the stack run scripts/setup_data.py from their own
    // credentials to create the index and load the catalog. It is scoped to
    // this collection and its indexes only. For production, replace it with a
    // dedicated, narrowly scoped data-loader role.
    // --------------------------------------------------------------
    const runtimeRoleArns = [runtime.role.roleArn];
    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'CollectionDataAccessPolicy', {
      name: 'coffee-products-access',
      type: 'data',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${COLLECTION_NAME}`],
              Permission: ['aoss:CreateCollectionItems', 'aoss:UpdateCollectionItems', 'aoss:DescribeCollectionItems'],
            },
            {
              ResourceType: 'index',
              Resource: [`index/${COLLECTION_NAME}/*`],
              Permission: [
                'aoss:CreateIndex',
                'aoss:DescribeIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument',
                'aoss:UpdateIndex',
                'aoss:DeleteIndex',
              ],
            },
          ],
          Principal: [...runtimeRoleArns, `arn:aws:iam::${this.account}:root`],
        },
      ]),
    });
    dataAccessPolicy.addDependency(collection);

    // --------------------------------------------------------------
    // Hand-written gateway -> runtime target (GATEWAY_IAM_ROLE outbound auth).
    //
    // The CLI schema only allows OAUTH/NONE outbound for mcpServer targets and
    // needs a static endpoint URL that does not exist until the in-project
    // runtime is deployed, so the target is a raw CfnGatewayTarget here.
    // --------------------------------------------------------------
    {
      const runtimeArn = runtimeEnv.runtime.runtimeArn;

      // Build the runtime invoke URL, URL-encoding the runtime ARN (`:` -> %3A,
      // `/` -> %2F) exactly like the @aws/agentcore-cdk getRuntimeEndpointUrl
      // helper. The nested Fn.split/Fn.join replaces every `:` with `%3A` and
      // every `/` with `%2F` in the ARN token, then Fn.sub assembles the URL.
      const runtimeInvokeEndpoint = Fn.sub(
        'https://bedrock-agentcore.${AWS::Region}.${AWS::URLSuffix}/runtimes/${EncodedArn}/invocations?qualifier=DEFAULT',
        {
          EncodedArn: Fn.join('%2F', Fn.split('/', Fn.join('%3A', Fn.split(':', runtimeArn)))),
        }
      );

      // Import the gateway's execution role so we can grant it permission to
      // invoke the runtime via SigV4 (the GATEWAY_IAM_ROLE outbound path).
      const gatewayRole = iam.Role.fromRoleArn(this, 'ImportedGatewayRole', gw.roleArn, { mutable: true });
      const invokeGrant = gatewayRole.addToPrincipalPolicy(
        new iam.PolicyStatement({
          actions: ['bedrock-agentcore:InvokeAgentRuntime'],
          resources: [runtimeArn, `${runtimeArn}/runtime-endpoint/*`],
        })
      );

      const cfnTarget = new bedrockagentcore.CfnGatewayTarget(this, 'CoffeeRuntimeTarget', {
        gatewayIdentifier: gw.attrGatewayIdentifier,
        name: GATEWAY_TARGET_NAME,
        targetConfiguration: {
          mcp: {
            mcpServer: {
              endpoint: runtimeInvokeEndpoint,
            },
          },
        },
        credentialProviderConfigurations: [
          {
            credentialProviderType: 'GATEWAY_IAM_ROLE',
            credentialProvider: {
              iamCredentialProvider: {
                service: 'bedrock-agentcore',
                region: this.region,
              },
            },
          },
        ],
      });

      // Create the target only after the gateway role can invoke the runtime.
      if (invokeGrant.policyDependable) {
        cfnTarget.node.addDependency(invokeGrant.policyDependable);
      }

      // Gateway MCP URL output (what the reader pastes into ChatGPT).
      new CfnOutput(this, 'GatewayMcpUrl', {
        value: gw.attrGatewayUrl,
        description: 'MCP URL to paste into ChatGPT (Authentication = None)',
      });
    }

    // --------------------------------------------------------------
    // CloudFormation outputs
    // --------------------------------------------------------------
    new CfnOutput(this, 'OpenSearchEndpoint', {
      value: collection.attrCollectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint',
    });
    new CfnOutput(this, 'ProductImagesBucketName', {
      value: bucket.bucketName,
      description: 'S3 bucket name for product images',
    });
    new CfnOutput(this, 'ProductImagesCDNDomain', {
      value: distribution.distributionDomainName,
      description: 'CloudFront distribution domain for product images',
    });
    new CfnOutput(this, 'ProductImagesCDNDistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront distribution ID (for cache invalidation)',
    });
    new CfnOutput(this, 'CartTableName', {
      value: cartTable.tableName,
      description: 'DynamoDB cart table name',
    });
  }

  /**
   * Create payment infrastructure via CFN constructs. Preserved verbatim from
   * the vended template; the Coffee Discovery project declares no payments, so
   * this is a no-op at synth time, but it is kept so a future `agentcore add
   * payment-manager` keeps working without re-deriving the stack.
   */
  private addPaymentInfrastructure(spec: AgentCoreProjectSpec, paymentSpec: PaymentSpec[] | undefined): void {
    // Create payment infrastructure via CFN constructs
    if (paymentSpec && paymentSpec.length > 0) {
      for (const payment of paymentSpec) {
        const mgrId = toCdkId(payment.name);
        const manager = new AgentCorePaymentManager(this, `Payment${mgrId}`, {
          projectName: spec.name,
          name: payment.name,
          authorizerType: payment.authorizerType,
          description: payment.description,
          authorizerConfiguration: payment.authorizerConfiguration,
          tags: spec.tags,
        });

        const prefix = `AGENTCORE_PAYMENT_${payment.name.toUpperCase().replace(/-/g, '_')}`;

        // Wire env vars from construct output tokens into eligible agent environments only.
        // See isPaymentEligibleAgent — non-Python or non-HTTP runtimes have no shim that
        // can consume these env vars, and giving them sts:AssumeRole on the
        // ProcessPaymentRole would broaden the privilege surface unnecessarily.
        for (const env of this.application.environments.values()) {
          if (!isPaymentEligibleAgent(env.agent)) {
            continue;
          }
          env.runtime.addEnvironmentVariable(`${prefix}_MANAGER_ARN`, manager.paymentManagerArn);
          env.runtime.addEnvironmentVariable(`${prefix}_PROCESS_PAYMENT_ROLE_ARN`, manager.processPaymentRoleArn);

          // Grant runtime execution role permission to assume the ProcessPaymentRole.
          // The ProcessPaymentRole's trust policy allows AccountRootPrincipal, but the
          // caller still needs sts:AssumeRole on its own role to perform the assumption.
          env.runtime.role.addToPrincipalPolicy(
            new iam.PolicyStatement({
              actions: ['sts:AssumeRole'],
              resources: [manager.processPaymentRoleArn],
            })
          );

          // Grant payment data-plane actions directly to the runtime role.
          //
          // NOTE: This deviates from the canonical role model in the AgentCore Payments
          // beta guide, which assigns Get/List/Create instrument+session actions to a
          // separate ManagementRole and limits the agent's role to ProcessPayment only.
          // The current SDK plugin (AgentCorePaymentsPlugin.generate_payment_header)
          // calls GetPaymentInstrument internally during the 402 auto-pay path, so the
          // runtime role needs read access. CreatePaymentSession is included so
          // `agentcore invoke --auto-session` works without a separate ManagementRole
          // call. Tighten this if the SDK is updated to accept pre-fetched instrument
          // details and split create-session into a backend-only flow.
          env.runtime.role.addToPrincipalPolicy(
            new iam.PolicyStatement({
              actions: [
                'bedrock-agentcore:GetPaymentInstrument',
                'bedrock-agentcore:ListPaymentInstruments',
                'bedrock-agentcore:GetPaymentInstrumentBalance',
                'bedrock-agentcore:GetPaymentSession',
                'bedrock-agentcore:ListPaymentSessions',
                'bedrock-agentcore:CreatePaymentSession',
                'bedrock-agentcore:ProcessPayment',
              ],
              resources: [manager.paymentManagerArn, `${manager.paymentManagerArn}/*`],
            })
          );

          if (payment.autoPayment !== undefined) {
            env.runtime.addEnvironmentVariable(`${prefix}_AUTO_PAYMENT`, String(payment.autoPayment));
          }
          if (payment.paymentToolAllowlist) {
            env.runtime.addEnvironmentVariable(`${prefix}_TOOL_ALLOWLIST`, payment.paymentToolAllowlist.join(','));
          }
          if (payment.networkPreferences) {
            env.runtime.addEnvironmentVariable(`${prefix}_NETWORK_PREFERENCES`, payment.networkPreferences.join(','));
          }
          if (payment.authorizerType === 'CUSTOM_JWT') {
            env.runtime.addEnvironmentVariable(`${prefix}_AUTH_MODE`, 'bearer');
          }
        }

        // Create connectors for this manager
        for (const connector of payment.connectors) {
          const connId = toCdkId(connector.name);
          const schemaConnector =
            connector.provisionMode === 'QUICK_CREATE'
              ? connector
              : {
                  name: connector.name,
                  provider: connector.provider,
                  ...(connector.provisionMode && { provisionMode: connector.provisionMode }),
                  credentialName: connector.credentialName,
                };
          const compatibilityProps = {
            projectName: spec.name,
            paymentManager: manager,
            connector: schemaConnector,
            // Remove these legacy manual fields after the new L3 release is pinned.
            connectorName: connector.name,
            connectorType: connector.provider,
            ...(connector.provisionMode !== 'QUICK_CREATE' && {
              credentialProviderArn: connector.credentialProviderArn,
            }),
          };
          const conn = new AgentCorePaymentConnector(
            this,
            `Payment${mgrId}${connId}`,
            compatibilityProps as unknown as ConstructorParameters<typeof AgentCorePaymentConnector>[2]
          );

          // Wire first connector's ID as env var (eligible agents only)
          if (connector === payment.connectors[0]) {
            for (const env of this.application.environments.values()) {
              if (!isPaymentEligibleAgent(env.agent)) continue;
              env.runtime.addEnvironmentVariable(`${prefix}_CONNECTOR_ID`, conn.paymentConnectorId);
            }
          }

          new CfnOutput(this, `Payment${mgrId}${connId}ConnectorId`, {
            value: conn.paymentConnectorId,
          });
          if (connector.provisionMode === 'QUICK_CREATE') {
            const quickCreateConnector = conn as AgentCorePaymentConnector & {
              paymentConnectorStatus: string;
              authorizationUrl: string;
            };
            new CfnOutput(this, `Payment${mgrId}${connId}ConnectorStatus`, {
              value: quickCreateConnector.paymentConnectorStatus,
            });
            new CfnOutput(this, `Payment${mgrId}${connId}AuthorizationUrl`, {
              value: quickCreateConnector.authorizationUrl,
            });
          }
        }

        // CFN Outputs for post-deploy state parsing
        new CfnOutput(this, `Payment${mgrId}ManagerArn`, {
          value: manager.paymentManagerArn,
        });
        new CfnOutput(this, `Payment${mgrId}ManagerId`, {
          value: manager.paymentManagerId,
        });
        new CfnOutput(this, `Payment${mgrId}ProcessPaymentRoleArn`, {
          value: manager.processPaymentRoleArn,
        });
        new CfnOutput(this, `Payment${mgrId}ResourceRetrievalRoleArn`, {
          value: manager.resourceRetrievalRoleArn,
        });
      }
    }

    // Stack-level output
    new CfnOutput(this, 'StackNameOutput', {
      description: 'Name of the CloudFormation Stack',
      value: this.stackName,
    });
  }
}
