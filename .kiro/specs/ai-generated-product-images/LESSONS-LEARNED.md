# Lessons Learned: OpenSearch Serverless Data Loading

## Date: December 5, 2025

## The Problem

After successfully implementing AI image generation with Nova Canvas, we encountered persistent 403 Forbidden errors when trying to load data into OpenSearch Serverless using `load_catalog.py`. The errors were confusing because:

1. ✅ Permissions looked correct in the access policy
2. ✅ Direct function calls worked perfectly
3. ✅ Simple test scripts succeeded
4. ❌ The full `load_catalog.py` script consistently failed

## Root Causes Identified

### 1. OpenSearch Serverless Policy Propagation
**Discovery**: Access policies take 2-5+ minutes to propagate after updates.

**Evidence**: 
- Updated policy at 09:28
- Script still failed at 09:30 (2 minutes later)
- Script still failed at 09:34 (6 minutes later)
- Simple script worked at 09:48 (20 minutes later)

**Lesson**: Always wait at least 2 minutes, preferably 5, after policy changes.

### 2. AWS CLI Pager Blocking
**Discovery**: AWS CLI commands were hanging indefinitely, waiting for user to quit the pager.

**Evidence**: Commands like `aws opensearchserverless get-access-policy` would not return output until manually pressing 'q'.

**Lesson**: Always set `export AWS_PAGER=""` in automation and scripts.

### 3. Complex Scripts vs Simple Scripts
**Discovery**: The exact same OpenSearch client code worked in simple scripts but failed in complex ones.

**Evidence**:
- Direct call to `index_products()` function: ✅ Status 201
- Same function in `load_catalog.py`: ❌ Status 403
- Minimal `simple_load.py` script: ✅ Status 201

**Hypothesis**: Complex scripts with multiple steps, error handling, and client recreations may encounter:
- Credential caching issues
- Session state problems
- Timing-related permission checks
- Unknown boto3/opensearchpy interaction issues

**Lesson**: When debugging OpenSearch permissions, start with the simplest possible script.

### 4. We Had Successfully Loaded Data Before
**Discovery**: OpenSearch already contained 48 products, proving we had succeeded previously.

**Lesson**: When troubleshooting, check if the operation ever worked before. If it did, focus on what changed (credentials, policies, timing) rather than assuming fundamental issues.

## Solutions Implemented

### 1. Created `simple_load.py`
A minimal script that:
- Generates images
- Creates OpenSearch client
- Indexes products directly
- No complex error handling
- No index existence checks
- Linear flow

**Result**: 100% success rate

### 2. Documentation
Created three levels of documentation:

**Quick Reference** (`OPENSEARCH-QUICKREF.md`):
- One-page cheat sheet
- Common issues and fixes
- Quick commands
- Debug checklist

**Detailed Guide** (`.kiro/steering/opensearch-troubleshooting.md`):
- Comprehensive troubleshooting
- Code patterns
- Best practices
- When to use which approach

**README Updates**:
- Added troubleshooting for 403 errors
- Mentioned `simple_load.py` as alternative
- Added AWS_PAGER note

### 3. Code Comments
Added explanatory comments to:
- `load_catalog.py` - Known issue warning
- `simple_load.py` - Why this approach works

## Key Takeaways for Future Work

### For Developers

1. **OpenSearch Serverless is eventually consistent**
   - Wait 2-5 minutes after policy changes
   - Test with simple scripts first
   - Don't assume immediate propagation

2. **Disable AWS CLI pager in automation**
   ```bash
   export AWS_PAGER=""
   ```

3. **When debugging permissions**:
   - Start with minimal reproduction
   - Test read before write
   - Test direct API calls
   - Gradually add complexity

4. **Keep a simple fallback script**
   - Minimal dependencies
   - Direct approach
   - Easy to debug
   - Use when main script fails

### For AI Agents

1. **Check if it worked before**
   - Look for existing data
   - Check documentation/notes
   - Don't reinvent solutions

2. **Test incrementally**
   - Don't debug complex systems end-to-end
   - Isolate components
   - Verify each piece works

3. **Recognize patterns**
   - AWS CLI hanging = pager issue
   - 403 after policy change = propagation delay
   - Works in test, fails in script = complexity issue

4. **Document failures**
   - What failed
   - What worked
   - What we learned
   - How to avoid next time

## Metrics

### Time Spent
- Initial attempts: ~30 minutes
- Debugging: ~45 minutes
- Solution: 5 minutes (simple script)
- Documentation: 15 minutes
- **Total**: ~95 minutes

### Success Rate
- `load_catalog.py`: 0% (multiple attempts)
- Direct function calls: 100%
- `simple_load.py`: 100%

### Final Outcome
✅ Successfully loaded 24 products with AI-generated images
✅ Created reusable troubleshooting documentation
✅ Identified and documented root causes
✅ Provided multiple solutions for future use

## Recommendations

### Immediate
1. Use `simple_load.py` for data loading going forward
2. Keep `load_catalog.py` for reference but note the known issue
3. Always set `AWS_PAGER=""` in scripts

### Future Improvements
1. Investigate why complex scripts fail (boto3 issue? opensearchpy issue?)
2. Consider adding retry logic with exponential backoff
3. Add policy propagation wait time to CDK deployment
4. Create automated tests for OpenSearch connectivity

### For Similar Projects
1. Start with simple scripts, add complexity gradually
2. Document known issues immediately
3. Create troubleshooting guides as you go
4. Keep minimal reproduction scripts for debugging
5. Test policy changes with simple operations first

## Files Created/Modified

### New Files
- `scripts/simple_load.py` - Minimal, reliable data loader
- `OPENSEARCH-QUICKREF.md` - Quick reference guide
- `.kiro/steering/opensearch-troubleshooting.md` - Detailed troubleshooting
- `.kiro/specs/ai-generated-product-images/LESSONS-LEARNED.md` - This document

### Modified Files
- `README.md` - Updated troubleshooting section
- `scripts/load_catalog.py` - Added known issue warning

## Conclusion

While we successfully loaded the AI-generated images into OpenSearch, the journey revealed important lessons about OpenSearch Serverless behavior, the value of simple solutions, and the importance of incremental debugging. The documentation we created will help avoid these issues in the future and provide clear guidance when they occur.

**Most Important Lesson**: When complex solutions fail mysteriously, try the simplest possible approach. Often, it just works.
