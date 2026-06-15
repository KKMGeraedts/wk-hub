# GenAI Service uses minimal normalized inputs

The GenAI Service calls a language model only with the smallest normalized data needed for a GenAI Job. It does not send raw provider payloads, participant prediction data, user identity data, or broad database context to the LLM provider. This keeps quiz-answer and player-matching assistance auditable, limits privacy exposure, and preserves the existing boundary where participant-facing reads do not trigger external calls.
