# Future Improvements

Ideas captured during evaluation — under consideration for future iterations.

## Analytics & data model

- **Expand the firmographic set at intake.** We don't yet capture age/location/entity-count/revenue at intake, so the cohort is industry + size band for now — expanding the firmographic set would be its own intake + schema task. (Note: after the chart-redesign PR merges, run a prod recompute so the new persona prose lands.)
- **Function vocabulary refinement.** The controlled list of functions offered on the intake form is a first pass; refine the taxonomy once real usage shows what people pick and what's missing.
- **Synthesize more data for cluster stability.** Per-grain clustering (function + company) has small-N limitations; more synthetic data will stabilize personas and silhouette scores.
- **Maturity score sophistication.** Maturity is currently a keyword/threshold heuristic (base 2.8 ± automation/SQL signals, close days, manual hours). Worth revisiting once there's enough data to validate or learn weights.

## Delivery & UX

- **Internal positioning map: bubble sizing vs. explainer.** The plot bubbles are size-capped at 130px so large personas fit, and the map explainer says "bigger bubble = more members" (the mock's text said "more mature" but its own code sized by members). The mock text was changed intentionally — rectify the implementation to match the intended design (size by maturity, update the explainer accordingly).
- **Aesthetics pass.** Deliberately deferred until deliverables are locked — the external and internal destinations are structure-first today.
- **Promote /hub to root.** The landing page lives at /hub with the chat still at root; decide which should be the front door.
- **External view auth.** Decide whether the external deliverable is a prospect self-serve link or vendor-presented; affects whether/how it's gated.
- **True PDF downloads.** Downloads are print-ready paginated HTML today; upgrade to real PDF generation if recipients need files that render identically everywhere.
- **Q&A chat on the Internal and External sites.** The information is dense; add a chat feature for quick questions against the page/report content.
- **Button-style table of contents on Internal and External.** Jump-to-section buttons for quicker navigation through the long pages.
- **Voice agent for chatbot.** Incorporate a voice agent that facilitates a verbal conversation as an alternative to a typing conversation.

## Recommendations & engagement

- **Expand the RAG with additional in-scope products.** Beyond the vendor capability doc, add other in-scope products to the RAG so roadmap recommendations can draw on them.
- **Recommend in-scope products (and the vendor's own) during the chat.** Surface relevant product recommendations throughout the intake conversation to keep the respondent engaged and investing in the effort.

## Ops & security

- **Rotate the admin token.** The current token has appeared in chats and URLs; rotate it once demos settle.
- **Fix the worker/migration deploy race.** On deploy, the worker job can start before the api service's pre-deploy migration step runs (crashed once on a missing column). Move migrations ahead of the worker too, or make the worker retry.

## Predictions

- **Predict buying propensity.** Track transition from prospect to client to identify buying signals. Build an ML model to predict likelihood to buy.