# TOEIC AI Question Generation Guidelines

> **Purpose:** System-level specification for an AI Agent that generates, validates, and quality-controls TOEIC Listening & Reading questions.
>
> **Primary goal:** Generate questions that are faithful to the TOEIC format, natural in English, unambiguous, appropriately difficult, and supported entirely by the supplied source material.
>
> **Important:** These rules are intended to guide an AI agent. They are stricter than ordinary "make a plausible question" instructions because generated content will be used in an actual TOEIC practice application.

---

# 1. Core Principles

The agent must follow these principles for **every question**.

## 1.1 Source-grounded generation

Every question and every answer choice must be supported by the supplied source.

- Do not introduce facts that are not in the source.
- Do not require outside knowledge.
- Do not invent names, dates, prices, locations, reasons, policies, or relationships.
- Do not infer information unless the inference is clearly and naturally supported by the source.
- The correct answer must be demonstrably supported by the source.

For Listening:

> The answer must be recoverable from the audio/transcript alone.

For Reading:

> The answer must be recoverable from the supplied reading passage, notice, email, advertisement, article, or other text.

---

## 1.2 One unambiguous correct answer

Every multiple-choice question must have exactly **one defensible correct answer**.

Reject a question if:

- two options could reasonably be correct;
- an option is true but less specific than another option in a way that creates ambiguity;
- the question depends on an unstated assumption;
- the wording allows multiple interpretations;
- the source itself is ambiguous.

When in doubt, rewrite the question.

---

## 1.3 Distractors must be plausible

Do not create obviously incorrect distractors.

Prefer distractors that are:

- mentioned in the source;
- semantically related to the correct answer;
- associated with the same topic;
- associated with a different person;
- associated with a different location;
- associated with a different time;
- associated with a different purpose;
- associated with a different condition;
- associated with a different event.

A strong distractor is usually:

> **True information + wrong relationship**

rather than:

> **Completely unrelated information**

Example:

Source:

> The online safety quiz must be completed before entering the production floor.

Question:

> What is required in the production area?

Weak distractor:

> (B) Buying a new computer

Strong distractor:

> (B) Completing an online quiz

The second distractor is stronger because it is genuinely grounded in the source but wrong because of **timing/context**.

---

## 1.4 Do not make the correct answer identifiable by style

The correct answer must not stand out because it:

- is longer than every other option;
- uses more precise vocabulary;
- contains unusually detailed information;
- uses noticeably different grammar;
- uses wording copied directly from the source while distractors are paraphrased;
- is the only grammatically complete option.

Keep options structurally parallel.

---

## 1.5 Avoid unnecessary keyword matching

Do not design every question so that the student only needs to hear/read one keyword.

Good TOEIC items often require the learner to connect:

- a fact with its purpose;
- an action with its time;
- a person with an action;
- an offer with its condition;
- an object with its location;
- a problem with its proposed solution;
- a statement with an implied meaning.

Use direct retrieval where appropriate, but create a mixture of cognitive demands.

---

# 2. TOEIC Listening Question Generation

The Listening section consists of:

- Part 1 — Photographs
- Part 2 — Question-Response
- Part 3 — Conversations
- Part 4 — Talks

The agent must treat each part as a different item type.

---

# 3. Part 1 — Photographs

## 3.1 Purpose

Part 1 tests the ability to understand short descriptions of what is happening in a photograph.

The question is represented by an audio statement, and the learner chooses the statement that best describes the photograph.

The central requirement is:

> The statement must describe something that is visibly supported by the image.

---

## 3.2 What to test

Prefer visible information such as:

- people;
- objects;
- actions;
- positions;
- locations;
- relationships between objects;
- physical conditions;
- visible states.

Examples:

- A woman is standing beside a counter.
- Some chairs are arranged around a table.
- A man is loading boxes onto a truck.
- Several bicycles are parked outside a building.

---

## 3.3 Do not test invisible information

Do not generate statements about:

- intentions;
- thoughts;
- names;
- occupations unless visually obvious and conventionally inferable;
- future actions;
- reasons;
- ownership;
- exact time;
- unseen objects;
- events outside the photograph.

Bad:

> The woman is waiting for her manager.

The image cannot establish this.

Better:

> The woman is looking at a computer screen.

---

## 3.4 Preferred Part 1 distractor types

### Type A — Wrong action

Image:

> A man is carrying a box.

Distractor:

> The man is putting a box on a shelf.

Both actions are plausible, but only one matches the image.

### Type B — Wrong object

Image contains:

> chairs

Distractor:

> The chairs are being moved.

if no movement is visible.

### Type C — Wrong location

Image:

> A bicycle is beside a building.

Distractor:

> A bicycle is inside the building.

### Type D — Wrong subject

Image:

> A woman is opening a cabinet.

Distractor:

> A man is opening a cabinet.

### Type E — Wrong relationship

Image:

> Books are on a desk.

Distractor:

> Books are under the desk.

---

## 3.5 Part 1 linguistic rules

Statements should be:

- concise;
- grammatically complete;
- natural spoken English;
- visually verifiable;
- similar in length.

Avoid unnecessarily complicated vocabulary.

Do not make the correct answer easier because it contains a unique noun visible in the picture while all distractors use vague language.

---

## 3.6 Part 1 validation

Before accepting an item, ask:

1. Is every part of the correct statement visible?
2. Could the image support another option?
3. Does any distractor describe something actually visible?
4. Is the statement natural spoken English?
5. Is the action/state visually distinguishable?
6. Does the item test observation rather than outside knowledge?

If any answer creates ambiguity, reject or revise.

---

# 4. Part 2 — Question-Response

## 4.1 Purpose

Part 2 tests whether the learner can understand a spoken question/statement and select the most appropriate response.

The key principle is:

> The correct response must be conversationally appropriate, not merely lexically related.

---

# 4.2 Question types

Generate a balanced mixture of:

- Who
- What
- Where
- When
- Why
- How
- How often
- How much
- How long
- Yes/No questions
- Alternative questions
- Statements requiring an appropriate response
- Requests
- Suggestions
- Invitations
- Offers

---

# 4.3 WH-question rules

## Who

Question:

> Who will lead the meeting?

Good response:

> Ms. Chen from the sales department.

Bad response:

> At three o'clock.

---

## Where

Question:

> Where should I leave these documents?

Good:

> On the reception desk.

Bad:

> Tomorrow morning.

---

## When

Question:

> When will the shipment arrive?

Good:

> On Thursday afternoon.

Bad:

> At the loading dock.

---

## Why

Question:

> Why was the meeting postponed?

Good:

> The manager is out of town.

Bad:

> In the conference room.

---

## How

Question:

> How can I update my contact information?

Good:

> Through the employee portal.

---

# 4.4 Yes/No questions

Do not require the response to literally begin with "Yes" or "No."

Natural responses are preferred.

Question:

> Did you send the invoice?

Possible correct response:

> I left it on your desk this morning.

This can be appropriate because it implies the invoice was sent/handled in the conversational context.

However, avoid responses that require excessive inference.

---

# 4.5 Indirect responses

TOEIC Part 2 frequently rewards understanding the intended meaning rather than matching words.

Question:

> Could you help me move these chairs?

Good:

> Sure. Where should I put them?

This is better than:

> Yes, the chairs are heavy.

---

# 4.6 Avoid lexical traps that create ambiguity

Bad design:

Question:

> Where is the printer?

A:

> It's near the window.

B:

> I printed the report.

If both are conversationally plausible, the item may be ambiguous.

Distractors should be inappropriate, not merely different.

---

# 4.7 Part 2 distractor categories

Useful distractor types:

- same keyword, wrong question type;
- related topic, wrong response;
- grammatically valid but conversationally inappropriate;
- answer to another WH-question;
- response associated with a different detail.

Example:

> When is the meeting?

A. In the main conference room.  
B. At 2 p.m.  
C. Mr. Lee is attending.  
D. Because the manager requested it.

Only B answers the question.

---

# 4.8 Part 2 difficulty

Easy:

- direct question → direct answer.

Medium:

- paraphrased response;
- indirect response;
- answer requires contextual interpretation.

Hard:

- natural conversational response;
- no repeated keywords;
- indirect but strongly supported answer;
- distractors contain keywords from the question.

Do not make every Part 2 question difficult through unnatural dialogue.

---

# 5. Part 3 — Conversations

## 5.1 Purpose

Part 3 tests comprehension of conversations between two or more speakers.

Questions should test:

- main purpose;
- specific information;
- speaker identity;
- location;
- problem;
- proposed solution;
- next action;
- reason;
- implication;
- change in plans;
- relationship between speakers.

---

# 5.2 Conversation structure

A useful generated conversation should contain a natural information progression:

```text
Situation
    ↓
Problem / request / topic
    ↓
Discussion
    ↓
Decision / solution / next step
```

Do not write conversations as unnatural question-answer data dumps.

Bad:

> A: What is the meeting about?  
> B: It is about the schedule.  
> A: What is the schedule?  
> B: It is the schedule for Friday.

Better:

> A: Have you seen the revised schedule for Friday?  
> B: Not yet. I thought the meeting was going to be postponed.  
> A: It was, but Ms. Lee moved it back to 3 p.m.

---

# 5.3 Part 3 question types

For a three-question set, prefer a mixture such as:

```text
Q1 → Purpose / situation
Q2 → Specific information
Q3 → Next action / inference
```

or:

```text
Q1 → Problem
Q2 → Specific detail
Q3 → What will the speaker do next?
```

Avoid three questions that all test the same sentence.

---

# 5.4 Speaker identification

Questions:

> Who most likely is the man?

> Who is the woman?

The answer must be supported by:

- occupation;
- role;
- relationship;
- actions;
- explicit introduction.

Do not infer an occupation from a weak clue.

---

# 5.5 Purpose questions

Purpose questions should reflect the overall conversation.

Good:

> Why does the man call the woman?

Bad:

> Why does the man call the woman?

Answer:

> Because the office is large.

if the conversation never establishes that this is the purpose.

Purpose should summarize the interaction.

---

# 5.6 Specific information

Questions may target:

- dates;
- times;
- prices;
- locations;
- products;
- schedules;
- instructions;
- quantities;
- names;
- services.

The correct answer must be explicit or strongly supported.

---

# 5.7 Next-action questions

Use the final part of the conversation.

Examples:

> What will the woman probably do next?

> What does the man plan to do?

The answer should follow naturally from the final decision or instruction.

Avoid speculative answers.

Bad:

> He will probably go home.

unless supported by the conversation.

---

# 5.8 Inference questions

Inference should be **local and constrained**.

Good:

Conversation:

> A: The printer isn't working again.  
> B: I'll call the technician.

Question:

> What problem are the speakers discussing?

Answer:

> A malfunctioning printer.

Bad inference:

> The company has poor maintenance policies.

This goes beyond the source.

---

# 5.9 Part 3 distractors

Strong distractors can be derived from:

- information said by the other speaker;
- information from a different point in the conversation;
- an action that was considered but rejected;
- a previous plan that was changed;
- a location mentioned for another purpose;
- a number/date associated with another event.

Especially valuable:

> **changed-plan distractor**

Example:

> They originally planned to meet Tuesday, but the meeting was moved to Wednesday.

Question:

> When will they meet?

Distractor:

> Tuesday.

This is an excellent distractor because it is real information but outdated.

---

# 5.10 Part 3 answer-choice rules

All four options should:

- have the same grammatical form;
- be similar in specificity;
- be plausible;
- be grounded in the conversation when possible.

Avoid one option being obviously unrelated.

---

# 6. Part 4 — Talks

## 6.1 Purpose

Part 4 contains a single speaker delivering a talk such as:

- announcements;
- advertisements;
- public notices;
- instructions;
- news reports;
- recorded messages;
- tours;
- introductions;
- workplace talks;
- event information;
- training/orientation talks.

---

# 6.2 Recommended talk structure

A strong generated Part 4 talk usually follows:

```text
Context
   ↓
Speaker / organization
   ↓
Main topic
   ↓
Important details
   ↓
Action / instruction / future event
   ↓
Closing
```

The script should sound like something a real person would say.

---

# 6.3 Part 4 question types

Use a mixture of:

### Purpose

> What is the purpose of the talk?

### Speaker identity

> Who is the speaker?

> Who most likely is the speaker?

### Specific information

> What is required?

> What service is available?

### Location

> Where can listeners...?

### Time

> When will...?

### Reason

> Why does the speaker mention...?

### Next action

> What should listeners do next?

### Future event

> What will happen tomorrow?

### Inference

> What is suggested about...?

---

# 6.4 Purpose questions

The purpose must represent the whole talk, not one isolated detail.

Good:

Talk:

> New fitness center opening + membership promotion + registration instructions.

Answer:

> To announce a promotion for a new fitness center.

Bad:

> To explain how to use the pool.

because the pool is only one detail.

---

# 6.5 Specific information questions

Target information that matters in the talk.

Good targets:

- price;
- deadline;
- location;
- schedule;
- requirements;
- included services;
- contact method;
- procedure.

---

# 6.6 Part 4 paraphrase

Paraphrase is encouraged.

Example:

Audio:

> attend a practical fire drill

Answer:

> Take part in a safety exercise

This is acceptable if the meaning remains clear.

Prefer natural semantic paraphrases.

Avoid:

- obscure synonyms;
- unnatural vocabulary;
- paraphrases that become broader than the source to the point of ambiguity.

---

# 6.7 Part 4 distractors

Excellent distractors often come from different information nodes in the same talk.

Example:

Talk contains:

```text
online quiz
protective equipment
second floor
fire drill
```

Question:

> What is required in the production area?

Options can use:

- online quiz;
- protective equipment;
- second floor;
- fire drill.

This creates plausible distractors because every option is grounded in the talk.

However, each distractor must be incorrect because of:

- time;
- location;
- purpose;
- condition;
- relationship;
- event;
- person.

---

# 6.8 Part 4 difficulty

Easy:

- explicit information;
- direct retrieval.

Medium:

- paraphrase;
- information from different parts of the talk;
- temporal/location distinction.

Hard:

- purpose;
- inference;
- relationship between details;
- indirect implication;
- changed conditions.

A good set should not contain only direct-retrieval questions.

---

# 7. TOEIC Reading Part 5 — Incomplete Sentences

## 7.1 Purpose

Part 5 primarily tests knowledge of:

- grammar;
- vocabulary;
- word forms;
- collocations;
- sentence structure;
- usage.

---

# 7.2 Grammar item construction

A strong grammar question should have:

1. one clear grammatical target;
2. a natural sentence;
3. enough context;
4. exactly one correct answer;
5. distractors that represent realistic learner errors.

---

# 7.3 Common grammar categories

Generate a balanced distribution of:

- parts of speech;
- subject-verb agreement;
- verb tense;
- active/passive voice;
- infinitives;
- gerunds;
- participles;
- modal verbs;
- conditionals;
- relative clauses;
- conjunctions;
- prepositions;
- articles;
- pronouns;
- determiners;
- comparatives;
- adverbs;
- adjectives;
- parallel structure;
- noun clauses;
- reduced clauses.

---

# 7.4 Parts-of-speech questions

Example:

> The company has experienced a significant ______ in sales.

A. increase  
B. increasingly  
C. increased  
D. increasing

Correct:

> A. increase

The blank requires a noun.

---

# 7.5 Word-form distractors

Word-form distractors should belong to the same lexical family when appropriate.

Example:

> The manager spoke ______ about the new policy.

A. confidence  
B. confident  
C. confidently  
D. confide

This tests form rather than unrelated vocabulary.

---

# 7.6 Verb tense questions

Provide a contextual time signal when necessary.

Good:

> The company ______ the new system last month.

A. introduces  
B. introduced  
C. has introduced  
D. introducing

"last month" strongly establishes past time.

Avoid creating questions where multiple tenses could be grammatically acceptable.

---

# 7.7 Preposition questions

Test natural usage rather than arbitrary memorization.

Good:

> The report must be submitted ______ Friday.

A. by  
B. during  
C. among  
D. beside

---

# 7.8 Vocabulary questions

Vocabulary questions should provide enough semantic context.

Bad:

> The company will ______ the new system.

A. implement  
B. install  
C. execute  
D. perform

if multiple options could reasonably fit.

Better:

> The company will ______ a new software system next month.

with context that makes the intended collocation clear.

---

# 7.9 Part 5 anti-ambiguity rule

Before accepting, replace the correct answer mentally with every distractor.

If more than one produces a natural sentence with the intended meaning, reject.

---

# 8. TOEIC Reading Part 6 — Text Completion

## 8.1 Purpose

Part 6 tests comprehension at the text/discourse level in addition to grammar and vocabulary.

The agent must consider surrounding sentences.

---

# 8.2 Passage structure

Use realistic business/workplace genres:

- email;
- notice;
- memo;
- advertisement;
- announcement;
- article;
- letter;
- instructions.

---

# 8.3 Four-question structure

A strong Part 6 set can contain:

```text
Q1 → Grammar
Q2 → Vocabulary
Q3 → Cohesion / sentence connection
Q4 → Text-level meaning
```

Do not make all four questions grammar questions.

---

# 8.4 Sentence insertion

When testing a missing sentence, the correct answer must fit:

- grammar;
- meaning;
- discourse flow;
- reference words;
- chronology;
- tone.

Look for clues such as:

- however;
- therefore;
- in addition;
- this;
- these;
- such;
- as a result;
- previously;
- next;
- finally.

---

# 8.5 Sentence-level cohesion

Example:

> The renovation will begin next Monday. ______. Employees should therefore use the temporary entrance.

A correct sentence might explain:

> The main entrance will be closed during the work.

The answer must connect naturally to the next sentence.

---

# 8.6 Part 6 distractors

Distractors can be:

- grammatically correct but contextually wrong;
- semantically related but incompatible;
- correct in isolation but inconsistent with the paragraph;
- wrong because of chronology;
- wrong because of referent;
- wrong because of tone.

---

# 9. TOEIC Reading Part 7 — Reading Comprehension

## 9.1 Purpose

Part 7 tests comprehension of realistic written material.

Common text types:

- emails;
- notices;
- advertisements;
- articles;
- messages;
- forms;
- schedules;
- instructions;
- reviews;
- web pages;
- business correspondence.

---

# 9.2 Question types

Use a balanced mixture of:

- main purpose;
- main idea;
- specific detail;
- NOT/TRUE questions;
- inference;
- vocabulary in context;
- reference;
- paraphrase;
- location;
- implied information;
- cross-text synthesis.

---

# 9.3 Single-passage questions

For a short passage, questions should progressively test:

```text
Q1 → Overall purpose
Q2 → Specific detail
Q3 → Paraphrase / inference
```

Avoid asking three questions about the same sentence.

---

# 9.4 Double-passage questions

Questions should sometimes require information from both texts.

Good:

> What is indicated about the meeting in the e-mail?

Bad:

> What time is the meeting?

if only one document is needed and the second document is irrelevant.

At least one question in a double-passage set should preferably test the relationship between the two texts.

---

# 9.5 Triple-passage questions

Use cross-document reasoning.

Potential relationships:

- email + advertisement;
- notice + schedule;
- article + survey;
- memo + form;
- announcement + response.

Strong question:

> Why does Mr. Lee mention the information in the second document?

or:

> What change is indicated by the two notices?

---

# 9.6 Reference questions

Example:

> The word "they" in paragraph 2 refers to:

The antecedent must be clear.

Avoid cases where two plural nouns could grammatically be the referent.

---

# 9.7 Vocabulary-in-context questions

Do not ask for a dictionary definition unrelated to the passage.

Question:

> The word "address" in paragraph 2 is closest in meaning to:

The intended meaning must be determined from context.

The correct answer should represent the contextual sense, not necessarily the most common dictionary sense.

---

# 9.8 Inference questions

Inference must remain evidence-based.

Good:

> What is suggested about the company's new policy?

when the passage provides clues.

Bad:

> What will the company probably do five years from now?

unless supported by the passage.

---

# 9.9 NOT questions

Use sparingly.

Example:

> Which of the following is NOT mentioned in the notice?

All four options should be plausible and related to the passage.

Three should be clearly supported; one should not.

Do not use "NOT" questions simply to increase difficulty.

---

# 10. Cross-Part Difficulty Framework

Difficulty should not be determined only by vocabulary.

Evaluate difficulty using:

### D1 — Retrieval distance

How far apart are the clues?

Low:

> Question and answer come from the same sentence.

High:

> Answer requires combining information from multiple sentences.

### D2 — Paraphrase distance

Low:

> Audio: "50 percent off"  
> Answer: "50 percent discount"

High:

> Audio: "bring a friend and both receive a free towel"  
> Answer: "The promotion provides an additional benefit for referrals."

### D3 — Inference depth

Low:

> Explicit fact.

Medium:

> Local inference.

High:

> Multiple pieces of evidence must be combined.

### D4 — Distractor similarity

Easy:

> Distractors are clearly different.

Hard:

> Distractors are all closely related and grounded in the source.

### D5 — Linguistic complexity

Consider:

- syntax;
- vocabulary;
- clause density;
- speech rate for listening;
- discourse structure.

Do not use difficult vocabulary alone to create a "hard" question.

---

# 11. Distractor Quality Framework

Every distractor should ideally receive a classification.

Allowed categories:

```text
WRONG_TIME
WRONG_LOCATION
WRONG_PERSON
WRONG_EVENT
WRONG_PURPOSE
WRONG_CONDITION
WRONG_RELATIONSHIP
WRONG_SCOPE
WRONG_QUANTITY
WRONG_SEQUENCE
WRONG_REFERENCE
WRONG_INFERENCE
RELATED_BUT_UNSUPPORTED
```

Preferred hierarchy:

### Tier 1 — Excellent

Source-grounded + plausible + clearly wrong for a specific reason.

### Tier 2 — Good

Source-grounded + plausible, but the reason for incorrectness is straightforward.

### Tier 3 — Acceptable

Semantically related but not directly stated.

### Tier 4 — Weak

Obviously unrelated or easily eliminated.

Avoid Tier 4 whenever possible.

---

# 12. Option Construction Rules

For four-option questions:

- exactly one correct answer;
- all options must be grammatically parallel;
- similar length;
- similar specificity;
- similar register;
- no accidental clues.

Avoid:

```text
(A) Yes.
(B) At the front desk.
(C) The manager will probably ask the employees to complete the form before the meeting.
(D) No.
```

Option C is obviously suspicious because of length and structure.

Prefer:

```text
(A) At the front desk
(B) In the main office
(C) Near the parking lot
(D) On the second floor
```

---

# 13. Explanation Generation Rules

Every generated question should have a concise evidence-based explanation.

The explanation must:

1. identify why the correct answer is correct;
2. reference the relevant source evidence;
3. explain why distractors are wrong when appropriate;
4. avoid introducing new information;
5. avoid over-explaining obvious grammar.

Recommended format:

```text
Correct answer: B.

Evidence:
"The discount includes personal training, group classes, and pool access."

Why B:
It directly identifies the services covered by the discount.

Why the others are wrong:
A refers to a separate promotional benefit.
C refers to locations.
D refers to other information in the announcement.
```

---

# 14. Explanation Quality Rules

Do not write explanations like:

> B is correct because B is correct.

Do not claim:

> The passage says...

when it does not.

Do not use evidence that merely resembles the answer.

Every explanation must be traceable to the source.

---

# 15. AI Generation Workflow

The agent should not generate the final item in a single unconstrained step.

Recommended pipeline:

```text
SOURCE
  ↓
SOURCE ANALYSIS
  ↓
INFORMATION MAP
  ↓
QUESTION PLAN
  ↓
QUESTION GENERATION
  ↓
DISTRACTOR GENERATION
  ↓
SELF-VALIDATION
  ↓
DIFFICULTY ESTIMATION
  ↓
QUALITY REVIEW
  ↓
PASS / REVIEW / REJECT
```

---

# 16. Step 1 — Source Analysis

Before generating questions, extract:

```json
{
  "topic": "",
  "genre": "",
  "speaker_roles": [],
  "people": [],
  "locations": [],
  "dates": [],
  "times": [],
  "numbers": [],
  "events": [],
  "actions": [],
  "requirements": [],
  "reasons": [],
  "problems": [],
  "solutions": [],
  "future_actions": [],
  "conditions": [],
  "promotions": [],
  "relationships": []
}
```

Only include information actually supported by the source.

---

# 17. Step 2 — Build an Information Map

Example:

```text
Information node 1:
New fitness center
→ opens Saturday
→ old market square

Information node 2:
Membership promotion
→ 50% off
→ first three months

Information node 3:
Included services
→ personal training
→ group classes
→ pool access

Information node 4:
Referral promotion
→ bring a friend
→ both receive free towel

Information node 5:
Deadline
→ next Friday
→ visit front desk

Information node 6:
Online registration
→ text OPEN
→ announced number
```

This prevents the model from repeatedly targeting the same sentence.

---

# 18. Step 3 — Question Planning

Before writing questions, decide:

```json
{
  "question_count": 3,
  "question_types": [
    "purpose",
    "specific_information",
    "action"
  ],
  "difficulty_distribution": [
    "medium",
    "easy",
    "easy_medium"
  ]
}
```

Do not generate three questions first and classify them afterward.

Plan the set first.

---

# 19. Step 4 — Generate the Correct Answer

Generate the correct answer from a specific information node.

Record:

```json
{
  "correct_answer": "C",
  "source_evidence": "...",
  "question_type": "purpose"
}
```

The evidence must be sufficient to prove the answer.

---

# 20. Step 5 — Generate Distractors

For every distractor, record:

```json
{
  "text": "...",
  "grounding": "...",
  "error_type": "WRONG_TIME"
}
```

Do not generate distractors blindly.

The model should know:

> What source information makes this distractor plausible?

and:

> Why is it definitely incorrect?

If either cannot be answered, replace the distractor.

---

# 21. Step 6 — Self-Validation

Before returning an item, the agent must test:

### Correctness

- Is the correct answer explicitly or strongly supported?
- Is there exactly one correct answer?

### Distractors

- Is every distractor definitely wrong?
- Could a reasonable learner defend another option?
- Are distractors grounded in the source where possible?

### Language

- Is the English natural?
- Is grammar correct?
- Are options parallel?

### TOEIC fit

- Does the item fit the requested Part?
- Does it test the intended skill?
- Is the question type appropriate?

### Difficulty

- Is the item too easy because of keyword matching?
- Is it artificially difficult because of obscure wording?
- Are distractors sufficiently plausible?

### Source integrity

- Did the agent invent anything?
- Does the explanation remain source-grounded?

---

# 22. Automated Quality Gate

Each question should receive:

```json
{
  "source_grounded": true,
  "single_correct_answer": true,
  "natural_english": true,
  "part_compliant": true,
  "distractors_plausible": true,
  "distractors_source_grounded": true,
  "no_ambiguity": true,
  "appropriate_difficulty": true
}
```

All critical fields must be true.

Recommended critical gates:

```text
source_grounded = true
single_correct_answer = true
no_ambiguity = true
part_compliant = true
natural_english = true
```

If any critical gate fails:

> REJECT

If only difficulty or distractor quality is questionable:

> REVIEW

Otherwise:

> PASS

---

# 23. PASS / REVIEW / REJECT

## PASS

Use when:

- answer is clearly correct;
- distractors are clearly wrong;
- wording is natural;
- Part format is correct;
- no meaningful ambiguity exists.

## REVIEW

Use when:

- answer is probably correct but wording could be improved;
- distractors are somewhat weak;
- difficulty is questionable;
- paraphrase is slightly unnatural;
- question is valid but below target quality.

## REJECT

Use when:

- multiple answers are defensible;
- answer is unsupported;
- source contains insufficient information;
- question violates Part rules;
- important information was invented;
- English is unnatural;
- distractors are nonsensical;
- explanation contradicts the source.

---

# 24. Recommended Quality Score

Score each item from 0–5.

```text
Source grounding          0–5
Correctness               0–5
Single-answer clarity     0–5
Distractor quality        0–5
Natural English           0–5
Part compliance           0–5
Paraphrase quality        0–5
Difficulty calibration    0–5
Explanation quality       0–5
```

Total:

```text
45 points
```

Suggested thresholds:

```text
40–45 → GOLD
35–39 → PASS
30–34 → REVIEW
0–29  → REJECT
```

Critical rule:

> A high score cannot override a critical failure.

For example:

```text
44/45 but two correct answers
→ REJECT
```

---

# 25. GOLD Item Characteristics

A GOLD item should have:

- one unmistakable correct answer;
- natural English;
- realistic TOEIC context;
- plausible distractors;
- source-grounded distractors;
- meaningful paraphrase;
- appropriate difficulty;
- no accidental clues;
- concise explanation;
- clear testing purpose.

---

# 26. Avoid Common AI Failure Modes

## Failure 1 — Invented information

Source:

> The meeting is on Tuesday.

AI question:

> Why did the manager move the meeting to Tuesday?

Problem:

The source never says it was moved.

Action:

> REJECT.

---

## Failure 2 — Two correct answers

Question:

> What is available at the center?

A. Pool access  
B. Group classes

If both are explicitly available, the question is ambiguous.

Action:

Rewrite:

> What is included in the membership discount?

if the source supports that relationship.

---

## Failure 3 — Distractor not grounded

Question:

> What will the employee do?

A. Complete the form  
B. Call the manager  
C. Buy a new laptop  
D. Attend the meeting

If the laptop was never mentioned, C is a weak distractor.

Prefer a source-grounded alternative.

---

## Failure 4 — Keyword giveaway

Audio:

> The shipment will arrive on Thursday.

Question:

> When will the shipment arrive?

A. Thursday  
B. Friday  
C. Monday  
D. Tuesday

This is valid but easy.

Do not make every item this direct.

---

## Failure 5 — Artificial paraphrase

Audio:

> Text the word OPEN.

Bad answer:

> Transmit a lexical token through a mobile communication service.

This is technically related but completely unnatural.

Use:

> Send a text containing the word OPEN.

---

## Failure 6 — Excessive inference

Source:

> The printer is broken. I'll call the technician.

Bad question:

> What problem does the company have with its IT department?

The source does not establish a company-wide IT problem.

---

## Failure 7 — Explanation invents evidence

Bad:

> B is correct because the manager specifically says that the company has approved the new policy.

if the manager never says this.

The explanation must be derived from actual source evidence.

---

# 27. Set-Level Quality

Do not evaluate only individual questions.

Evaluate the **whole question set**.

For a listening passage with three questions, check:

### Coverage

Do questions target different information nodes?

### Variety

Are question types sufficiently varied?

### Difficulty

Is there a sensible mix?

### Redundancy

Are two questions essentially testing the same fact?

### Leakage

Does one question accidentally reveal the answer to another?

Example:

Q1:

> What service does the center provide?

A. Pool access

Q2:

> What is included in the discount?

A. Pool access, group classes, and personal training

Q1 has now partially leaked Q2.

Avoid this.

---

# 28. Information Leakage Rules

Questions in the same set must not make other questions easier unintentionally.

Avoid:

```text
Q1:
Where does the event take place?
A. City Hall

Q2:
What will happen at City Hall?
A. A job fair
```

if Q2's location is not otherwise needed and Q1 gives away a key clue.

This is not always invalid, but the agent should minimize unnecessary cross-question clues.

---

# 29. Listening Script Quality

For Parts 3 and 4, scripts must sound spoken.

Use:

- contractions when natural;
- discourse markers;
- natural transitions;
- realistic workplace vocabulary;
- realistic conversational turns.

Avoid:

> The purpose of this conversation is to discuss the following matter.

Prefer:

> I wanted to ask you about the new schedule.

---

# 30. Reading Text Quality

Reading passages should resemble authentic workplace/business material.

Use realistic:

- names;
- dates;
- prices;
- schedules;
- departments;
- services;
- requests;
- policies;
- announcements.

Avoid artificial passages written only to contain grammar targets.

For Part 5, grammar can be the main target.

For Part 6/7, the text should remain meaningful as a whole.

---

# 31. Vocabulary and Grammar Difficulty

Do not equate difficult vocabulary with difficult TOEIC questions.

Difficulty should come from a combination of:

```text
Vocabulary
+
Grammar
+
Sentence structure
+
Information density
+
Paraphrase
+
Inference
+
Distractor similarity
```

A question can use common vocabulary but still be difficult because the learner must connect information across the passage.

---

# 32. Output Schema

Recommended internal output:

```json
{
  "part": 4,
  "question": "What is the purpose of the talk?",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "answer": "C",
  "question_type": "purpose",
  "difficulty": "medium",
  "source_evidence": [
    "..."
  ],
  "distractor_analysis": {
    "A": {
      "grounding": "...",
      "error_type": "WRONG_PURPOSE"
    },
    "B": {
      "grounding": "...",
      "error_type": "WRONG_LOCATION"
    },
    "C": {
      "grounding": "...",
      "error_type": null
    },
    "D": {
      "grounding": "...",
      "error_type": "WRONG_RELATIONSHIP"
    }
  },
  "explanation": "...",
  "quality": {
    "score": 42,
    "status": "GOLD"
  }
}
```

The exact schema may be adapted to the application's database model.

---

# 33. Final Agent Instruction

Use the following as the final high-level instruction to the generation agent:

> Generate TOEIC questions according to the specified Part rules. Treat the supplied source as the sole factual authority. Do not invent information. Every correct answer must be directly or strongly supported by the source, and every question must have exactly one defensible correct answer.
>
> Construct distractors deliberately. Prefer distractors grounded in real source information but made incorrect through a different time, location, person, purpose, condition, event, relationship, quantity, sequence, scope, or inference. Avoid unrelated distractors whenever possible.
>
> Use natural, concise, professional English appropriate for TOEIC. Keep answer choices grammatically parallel and similar in length and specificity. Do not make the correct answer identifiable through wording, length, vocabulary, or direct copying.
>
> Respect the specific skill and format of each TOEIC Part. Do not treat Parts 1–7 as interchangeable. Use the correct question types, discourse structure, difficulty, and distractor strategies for each Part.
>
> For Listening Parts 3 and 4, create natural spoken content and vary questions across purpose, specific information, speaker identity, location, time, reason, next action, and inference. For Reading Parts 5–7, ensure that the item tests the intended grammar, vocabulary, discourse, or reading-comprehension skill rather than accidental ambiguity.
>
> Before returning an item, perform a strict self-review:
>
> 1. Is the answer supported by the source?
> 2. Is there exactly one correct answer?
> 3. Is every distractor definitely incorrect?
> 4. Are distractors plausible and preferably source-grounded?
> 5. Is the English natural?
> 6. Does the item conform to the requested TOEIC Part?
> 7. Does the question test the intended skill?
> 8. Is the difficulty appropriate?
> 9. Does the explanation accurately cite the source?
> 10. Is there any ambiguity, unsupported inference, accidental clue, or information leakage?
>
> If any critical condition fails, do not force the item through. Mark it REVIEW or REJECT and regenerate when possible.
>
> The goal is not merely to produce a question whose answer is technically correct. The goal is to produce a defensible, natural, source-grounded TOEIC item that can survive expert review.

---

# 34. Recommended Generation Architecture

For a production TOEIC application, prefer a multi-stage architecture:

```text
                    ┌──────────────────┐
                    │   Source Input   │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Source Analyzer  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Information Map  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Question Planner│
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Question Writer │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Distractor Maker│
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Item Validator  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Quality Scorer   │
                    └────────┬─────────┘
                             ↓
                 ┌───────────┼───────────┐
                 ↓           ↓           ↓
               GOLD        PASS        REVIEW
                                         ↓
                                      REGENERATE
```

This is preferable to:

```text
Source → one LLM call → final question
```

because generation and evaluation should be treated as separate responsibilities.

---

# 35. Production Recommendation

For a real TOEIC application, the safest architecture is:

```text
Generator Agent
      ↓
Deterministic checks
      ↓
Validator Agent
      ↓
Scoring Agent
      ↓
Human review for borderline items
      ↓
Question Bank
```

Use deterministic validation wherever possible.

Examples:

- exactly four options;
- answer must be A/B/C/D;
- no duplicate options;
- no empty fields;
- required metadata exists;
- question type matches Part;
- source evidence exists;
- explanation exists;
- no accidental answer mismatch.

Use an LLM validator for semantic checks:

- ambiguity;
- distractor plausibility;
- source grounding;
- paraphrase quality;
- difficulty;
- naturalness.

---

# 36. Final Principle

The most important rule for the entire system is:

> **Do not optimize for "Can the AI generate a question?" Optimize for "Would an experienced TOEIC item writer accept this question?"**

A good AI-generated TOEIC item should be:

```text
Correct
   +
Unambiguous
   +
Source-grounded
   +
Natural
   +
Plausible distractors
   +
Appropriate difficulty
   +
Correct TOEIC format
   +
Meaningful measurement of the intended skill
```

Only when all of these conditions are satisfied should the item enter the production question bank.
