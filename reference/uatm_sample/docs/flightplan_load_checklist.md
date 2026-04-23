# Flightplan Load Checklist

Updated: 2026-02-12

## Current Decision
- Keep the existing flightplan-folder Load implementation code in the repository.
- Temporarily disable the upload UI/buttons until the next update cycle.

## Temporary UI State
- [x] `Load` button disabled.
- [x] `Reset` button disabled.
- [x] Notice added in settings panel: `Scheduled for future update`.
- [x] Hidden folder picker control disabled by app initialization guard.

## TODO (Next Update)
- [ ] Define final scope for flightplan-folder mode (`leg`-based counters, completion semantics).
- [ ] Re-validate repeated aircraft operation chain across all uploaded CSV files.
- [ ] Finalize scheduler constraints (gate/FATO queue and turnaround policy).
- [ ] Re-enable upload controls after end-to-end QA pass.
- [ ] Add dedicated user-facing guide for flightplan upload format and validation rules.

## Notes
- No existing load/scheduling code was removed in this step.
- This change is a temporary product-state switch for stability and expectation management.
