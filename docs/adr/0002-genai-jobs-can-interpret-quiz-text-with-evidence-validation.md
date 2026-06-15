# GenAI Jobs can interpret quiz text with evidence validation

Quiz automation uses a GenAI Job that receives the quiz question, answer options, and normalized match facts instead of requiring explicit per-question resolver metadata. This trades some determinism for lower admin setup work and broader quiz coverage. To keep scoring trustworthy, a GenAI answer only becomes an automatic quiz label when it selects an existing option, reports high confidence, and cites evidence from the supplied match facts; otherwise the quiz remains unresolved and admins are notified.
