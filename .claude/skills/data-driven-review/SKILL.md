# Data-Driven Code Review

**Когда использовать:** При ревью ВСЕХ MR которые меняют логику с данными.

**Что это:** Проверяем что implementer протестировал на реальных данных со стенда, не только на unit test mocks.

---

## Mandatory Checklist

### Section 1: Verify Test Data Exists

```
Проверяем что implementer использовал реальные данные:

[ ] MR description mentions "Data-Driven Validation"?
    NO → Request it, don't review further

[ ] Test sample is documented?
    Expected: "Tested on: 100 real orders from stage-db"
    [ ] Has datasource (where data came from)
    [ ] Has record count (e.g., "100 records")
    [ ] Has sample output (paste actual response)

[ ] Sample is REAL, not mocked?
    Check for:
    - psql output (raw SQL query ✓)
    - Kafka consumer output (✓)
    - API response dump (✓)
    
    Red flags (REJECT):
    - "MockOrderRepository" ✗
    - "fixture from test/" ✗
    - "$this->getFakeData()" ✗
```

### Section 2: Verify Test Results

```
[ ] Code ran on sample data without errors?
    Expected message: "Processing: 100/100 OK"
    NOT: "Processing: 0/100 empty"

[ ] Result is NOT all empty/null?
    Acceptable: "93 imported OK, 7 with warnings"
    Unacceptable: "Result: null" or "Processed: 0 records"

[ ] Output matches spec?
    Compare:
    OpenAPI spec says:     Real response shows:
    - status: string       - status: string ✓
    - amount: required     - amount: NULL ✗ (DIVERGENCE!)
    
    If mismatch found:
    - Document in code comment with source
    - Create ticket to fix spec OR code
    - Don't approve until resolved
```

### Section 3: Verify Edge Cases

```
[ ] Empty response tested?
    [ ] "0 records" case: handled? logged?
    [ ] "NULL fields" case: handled? logged?
    [ ] "Empty arrays" case: handled? logged?

[ ] Scale tested?
    Expected: "Tested on 1, 100, and 10,000 records"
    Check performance: still <1s on 10K?

[ ] Errors handled?
    [ ] Connection timeout: what happens?
    [ ] Database error: fallback? log?
    [ ] Invalid data: skip? warn? error?
```

### Section 4: Verify E2E (if applicable)

```
If code touches multiple services (site → integration → oms):

[ ] Transaction traced end-to-end?
    Expected: "Traced transaction OMS-12345 through 3 services"
    
[ ] Data integrity confirmed?
    [ ] Order ID same in all 3 systems?
    [ ] Status synced correctly?
    [ ] No data loss?
    [ ] Timestamps logical?
```

### Section 5: Final Decision

```
All checks above PASSED?
→ Approve with comment: "Data-driven validation confirmed"

Any check FAILED?
→ Request changes:
   "Please run code on real stage data and document results.
    Expected: 100+ records, >90% success rate, format matches spec."
```

---

## Common Issues to Catch

### Issue 1: "Result is Empty"

```
Implementer says: "Unit tests pass"
But: Data-driven shows "Processed: 0/100"

STOP! Ask:
- Why did 0 records match?
- Is the query wrong?
- Is the spec wrong?
- Do we have any data on stage?

Don't approve until: result != 0 OR reason documented
```

### Issue 2: "Spec vs Reality Mismatch"

```
OpenAPI says: "status required"
Real data shows: 7% of records have status = null

STOP! Ask:
- Is spec outdated?
- Does code handle null?
- Should we update spec or code?

Don't approve until: mismatch resolved (comment added OR code fixed)
```

### Issue 3: "No E2E Trace"

```
Code touches: site + integration + OMS
But: implementer only tested unit tests

STOP! Ask:
- Can you trace one transaction through all 3?
- Does data actually flow correctly?
- Are there integration bugs we'd miss?

Don't approve until: E2E tested OR documented why not possible
```

### Issue 4: "Scale Testing Missing"

```
Code works on 10 records (unit test)
But: stage has 100K records

Ask:
- Does code still run in <1s on 10K?
- Does memory stay acceptable?
- Are there N+1 queries?

Don't approve until: performance verified on 10K+ records
```

---

## Comment Template

When requesting data-driven validation:

```
[DATA_VALIDATION] Missing real-data testing

**Проблема:** Code не протестирован на реальных данных

**Почему:** Unit tests work, but stage behavior unknown
- Could have N+1 queries
- Could have NULL fields not in unit tests
- Could have format mismatch with spec

**Решение:**
1. Get 100+ real records from stage
   ```bash
   psql -h stage-db -c "SELECT * FROM orders LIMIT 100" > sample.json
   ```

2. Run code on sample
   - Verify: result != empty
   - Verify: format matches OpenAPI
   - Measure: time on 10K records

3. Document in MR:
   ```
   ## Data-Driven Validation
   - Tested on: 100 real orders from stage
   - Result: 98/100 OK, 2 with null fields
   - Performance: 245ms for 100 records
   - Spec match: YES (fields match OpenAPI)
   ```

4. Re-request review when done
```

---

## Red Flags (Auto-Reject)

Never approve if:

```
❌ "Result: null" or "Processed: 0"
   → Code doesn't work on real data

❌ "Only unit tests pass"
   → Not enough verification

❌ Spec mismatch, not documented
   → Future bug waiting to happen

❌ No edge case testing
   → Will break on first NULL field

❌ "Can't test on stage"
   → Then how do we know it works?
   → Should be escalated to human
```

---

## Success Criteria

Approve ONLY when:

- ✅ Real data sample: 100+ records
- ✅ Test result: >90% success rate
- ✅ Format: matches OpenAPI spec (or divergence documented)
- ✅ Edge cases: tested (NULL, empty, error cases)
- ✅ Scale: verified on 10K+ records (if applicable)
- ✅ E2E: traced through all services (if multi-service)

---

## Integration with MR Workflow

```
MR workflow:
1. Implementer opens MR
2. CI runs unit tests
3. [REVIEWER] Asks for data-driven validation
4. Implementer adds validation report
5. [REVIEWER] Approves based on this checklist
6. MR merges
```

This ensures: **No surprises after merge!**
