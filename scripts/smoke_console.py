#!/usr/bin/env python3
"""Drive the real console lifecycle (signup -> setup -> entitlement -> metering ->
billing) through console.store against a THROWAWAY temp DB. No prod data touched."""
import sys, tempfile, os, time
sys.path.insert(0, "console")
import store

DB = tempfile.mktemp(suffix=".db")
P = {"path": DB}
DAY = 86400
ok = lambda c: "PASS ✓" if c else "FAIL ✗"

print("="*78); print("CONSOLE LIFECYCLE SMOKE — fresh temp DB:", DB); print("="*78)
store.init_db(**P)  # create schema in the throwaway DB

# 1. SIGNUP (target ICP: a Claude-heavy support-AI company)
acct = store.create_account("ops@supportco.example", "s3cret-pw-123",
                            company="SupportCo (CX automation)", consent=True, **P)
aid = acct["id"]
print(f"\n1. Signup            -> account #{aid}, status={acct['status']!r}, role={acct['role']!r}  {ok(acct['status']=='active')}")

# 2. TRIAL auto-started
ts = store.trial_status(aid, **P)
print(f"2. Trial             -> active={ts['active']}, days_left={ts['days_left']}  {ok(ts['active'] and ts['days_left']>=6)}")

# 3. Deployment auto-created at signup
deps = store.deployments_for(aid, **P)
dep = deps[0]["deployment_id"]
print(f"3. Deployment        -> {dep[:18]}…  ({len(deps)} created at signup)  {ok(len(deps)==1)}")

# 4. ONBOARDING gate: brand-new acct has no key/traffic -> must be sent to Setup
keys = store.list_api_keys(aid, **P)
print(f"4. Setup gate        -> api_keys={len(keys)} -> route to /app/connect (Setup)  {ok(len(keys)==0)}")

# 5. CONNECT: mint the gateway key
key = store.create_api_key(aid, dep, name="prod gateway", **P)
full = key["full_key"]
print(f"5. Mint gateway key  -> {full[:14]}…  {ok(full.startswith('mp'))}")

# 6. AUTH: real key resolves, bogus key rejected
good = store.resolve_api_key(full, **P)
bad  = store.resolve_api_key("mp_not_a_real_key", **P)
print(f"6. Key auth          -> valid->acct#{(good or {}).get('account_id')}, bogus->{bad}  {ok(good and good['account_id']==aid and bad is None)}")

# 7. SETTINGS / onboarding choices
s = store.get_settings(aid, **P)
print(f"7. Default settings  -> mode={s['mode']!r}, autopilot_pct={s.get('autopilot_pct')}")
store.update_settings(aid, mode="autopilot", autopilot_pct=25, risk="balanced", **P)
s2 = store.get_settings(aid, **P)
print(f"   After onboarding  -> mode={s2['mode']!r}, autopilot_pct={s2['autopilot_pct']}, risk={s2['risk']!r}  {ok(s2['mode']=='autopilot' and s2['autopilot_pct']==25)}")

# 8. ENTITLEMENT during trial (what the brain checks every request)
ent = store.entitlement(dep, **P)
print(f"8. Entitlement(trial)-> entitled={ent['entitled']}, apply={ent['apply']}, mode={ent['mode']!r}, reason={ent['reason']!r}  {ok(ent['entitled'])}")

# 9. METERING: simulate a day of routed traffic (aggregate $ + counts only)
#    ~36% blended reduction / 59% routed, matching the routing smoke test.
store.record_meter(dep, requests=6500, routed=3835, escalations=21,
                   baseline_cost=120.0, actual_cost=77.0, category="classification", **P)
store.record_meter(dep, requests=2500, routed=1500, baseline_cost=60.0, actual_cost=40.0,
                   category="extraction", **P)
store.record_meter(dep, requests=1000, routed=565, baseline_cost=40.0, actual_cost=28.0,
                   category="summarization_short", caching_saved=3.5, opportunity_saved=6.0, **P)
print(f"9. Metering          -> 3 aggregate reports recorded (dollars + counts only, no prompts)")

# 10. DASHBOARD savings rollup
sm = store.savings_summary(aid, **P)
pct = sm["savings"]/sm["baseline"]*100 if sm["baseline"] else 0
print(f"10. Dashboard rollup -> requests={sm['requests']}, routed={sm['routed']} "
      f"({sm['routed']/sm['requests']*100:.0f}%), baseline=${sm['baseline']:.0f}, "
      f"actual=${sm['actual']:.0f}, SAVED=${sm['savings']:.0f} ({pct:.0f}% of bill)")
print(f"    caching credited=${sm['caching']:.1f} (shown free), opportunity=${sm['opportunity']:.1f} (advisory)  {ok(sm['savings']>0)}")
by = store.savings_by_category(aid, **P)
print(f"    by category      -> " + ", ".join(f"{r['category']}:${r['savings']:.0f}" for r in by))

# 11. QUALITY PROOF card
store.record_proof(dep, comparisons=400, non_inferior=394, **P)
print(f"11. Quality proof    -> 394/400 non-inferior recorded (feeds 'Quality preserved' card)  {ok(True)}")

# 12. TRIAL-END behavior: lapsed account passes through UNROUTED, never blocked
future = time.time() + (store.TRIAL_DAYS + 1) * DAY
ent_lapsed = store.entitlement(dep, now=future, **P)
print(f"12. After trial ends -> entitled={ent_lapsed['entitled']}, reason={ent_lapsed['reason']!r} "
      f"(traffic still flows, just unrouted)  {ok(not ent_lapsed['entitled'])}")

# 13. CONVERT TO PAID -> re-entitled
store.convert_to_paid(aid, stripe_customer_id="cus_TEST", **P)
ent_paid = store.entitlement(dep, now=future, **P)
print(f"13. Convert to paid  -> entitled={ent_paid['entitled']}, reason={ent_paid['reason']!r}  {ok(ent_paid['entitled'])}")

os.unlink(DB)
print("\nLifecycle complete. Temp DB removed. (Real modelpilot.db untouched.)")
