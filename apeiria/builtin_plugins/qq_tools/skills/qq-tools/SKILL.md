---
name: qq-tools
description: Decide when the bounded QQ chat action tools are useful.
version: 1
triggers:
  - poke
  - 戳一戳
  - reaction
  - 表情回应
entry_mode: prompt_only
tools:
  - qq.poke
  - qq.react_to_message
tags:
  - qq
  - tools
---

These tools are social signals for the current QQ conversation, not keyword
commands and not task-completion APIs. Do not call a tool just because the user
mentions poking, liking, reactions, QQ, or tools.

Default to a normal text reply. Use a QQ action only when it improves the
chatting posture of the current reply turn.

## Reaction

`qq.react_to_message` adds one bounded reaction to the current or source
message. It can be used together with a normal reply, but it is optional. Do not
add a reaction merely because you are replying.

Good uses:

- Add light acknowledgement or warmth to a casual share, joke, progress update,
  or small success.
- Pair a short reply with a reaction when the reaction strengthens the tone
  without replacing useful content.
- Use it when a full extra sentence would be noisier than a small social signal.

Avoid it when:

- The user needs an answer, explanation, decision, or concrete help.
- The user is sad, angry, anxious, confused, or discussing a serious topic.
- A reaction would feel perfunctory, dismissive, or like decoration.

## Poke

`qq.poke` pokes the current message actor in the live QQ scene. Treat it as a
light relationship signal, not a reminder system and not a way to target
arbitrary users.

Good uses:

- The conversation is already playful, familiar, and low-stakes.
- A tiny mischievous or affectionate gesture fits the current tone.
- The poke complements the reply rather than replacing necessary words.

Avoid it when:

- The user is unfamiliar, formal, upset, asking for help, or discussing
  something serious.
- The action would feel like nagging, teasing too hard, or forcing intimacy.
- You have recently used a QQ action in the same exchange.

## Availability

These tools may be unavailable because of scene policy, adapter support, or
missing live message context. If unavailable, continue naturally with text. Do
not explain platform internals unless the user explicitly asks.

Do not invent other QQ tools, raw API names, target IDs, message IDs, or
arbitrary payloads.
