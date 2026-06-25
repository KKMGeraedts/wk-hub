# Knockout Prediction Result and Advancement Are Separate

Knockout Stage score predictions are judged against the 90-minute Prediction Result, excluding extra time and penalties, while bracket progression is resolved from the separate Advancing Team fact. API provider `goals` can include extra-time goals or penalty-decided totals, so using it as the single match result would make pool scoring incorrect even though it may describe who advanced. The app therefore stores provider totals as evidence/display data and uses explicit advancement data for `W73`/`L73`-style Bracket Slots.
