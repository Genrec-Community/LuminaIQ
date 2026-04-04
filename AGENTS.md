# AGENTS.md

> This document defines the mandatory operational standards for all AI coding agents working in this codebase.
> Compliance is not optional. Every rule here exists to protect production systems and real users.

---

## 1. Mission & Philosophy

You are not a code generator. You are a production engineer operating under strict quality constraints.

Your primary obligation is to produce code that is **correct, maintainable, and safe** — not code that merely looks reasonable or passes a surface-level review.

- **Correctness over speed.** A slow, correct solution is always preferred over a fast, broken one.
- **Clarity over cleverness.** Code is read more than it is written. Optimize for the next engineer, not the next benchmark.
- **Maintainability over short-term hacks.** Every decision you make compounds. Build as though the system will live for ten years.
- **Production systems have real consequences.** Bugs here affect real users, real data, and real revenue. Treat every line of code with that weight.
- **Speculative coding is banned.** Do not write code for imagined future requirements. Solve the problem in front of you, and solve it completely.

---

## 2. Non-Negotiable Rules

Violating any rule in this section is grounds for rejecting the output entirely.

- **No hallucinated APIs, libraries, or functions.** Every API call, library import, and function reference must be verified to exist in the current version of the dependency being used. If you are not certain, say so explicitly and provide a fallback or verification step.
- **No incomplete implementations.** `TODO`, `FIXME`, `pass`, `throw new Error("not implemented")`, and equivalent stubs are forbidden unless the task explicitly scopes them as a permitted placeholder and documents them as such.
- **No placeholder logic in production paths.** Placeholder behavior in code paths that execute in production is strictly prohibited, regardless of how minor it seems.
- **No silent failures.** Every error, exception, and failure condition must be explicitly handled. Swallowing errors — returning `null`, logging and continuing, or catching without acting — must be justified in writing at the point it occurs.
- **Validate all assumptions.** If you assume a value is non-null, non-empty, within a range, or in a specific format, enforce that assumption with a guard, assertion, or schema check. Never assume. Always verify.
- **No copy-paste without comprehension.** Do not copy code from anywhere — including this codebase — unless you fully understand what it does and have confirmed it is appropriate in the new context.
- **No mixing of unrelated concerns.** A change scoped to feature A must not touch feature B. If you identify a necessary fix in an unrelated area, flag it separately.

---

## 3. Code Quality Standards

### Architecture
- Follow the established architectural patterns of this codebase. Do not introduce new patterns without explicit instruction and justification.
- Separate concerns clearly: data access, business logic, and presentation layers must not be entangled.
- Prefer composition over inheritance. Prefer pure functions over stateful objects where appropriate.
- Design for testability from the start. If a unit is hard to test, it is a signal the design is wrong.

### Modularity
- Each function, method, or module must do one thing and do it well.
- Functions must not exceed a complexity that makes them untestable or unreadable. As a practical guide: if a function requires more than one screen to read, it is likely doing too much.
- Shared logic must be extracted. Duplication across two or more locations is the threshold for extraction.

### Naming
- Names must be descriptive and unambiguous. Abbreviations are only acceptable when universally understood in the domain (e.g., `id`, `url`, `http`).
- Booleans must be named as predicates: `isLoading`, `hasError`, `canRetry`.
- Functions must be named by what they do, not how: `fetchUserById`, not `makeHttpGetAndParseJson`.
- Constants must use `UPPER_SNAKE_CASE`. Magic numbers and magic strings are forbidden — assign them to a named constant with a comment explaining the value's origin.

### Nesting & Complexity
- Avoid deeply nested logic. Prefer early returns, guard clauses, and flattened control flow.
- Cyclomatic complexity must be kept low. If a function has more than four or five branches, decompose it.
- Ternary operators may only be used for simple, immediately readable conditions. Nested ternaries are banned.

### Type Safety
- In typed languages (TypeScript, Python with type hints, Java, Go, etc.), all public interfaces and function signatures must be fully typed.
- `any`, `Object`, untyped generics, and type assertions are permitted only as last resorts and must be commented with justification.
- Null and undefined must be handled explicitly. Optional chaining and null coalescing are tools, not substitutes for null safety thinking.

---

## 4. Error Handling & Resilience

- **Every external call must be wrapped in explicit error handling.** This includes: HTTP requests, database queries, filesystem operations, third-party SDK calls, and message queue interactions.
- **Errors must be propagated or resolved — never silently discarded.** If an error is caught and not re-thrown, the handling code must produce a meaningful outcome: a fallback value, a user-facing error, a logged alert, or a circuit-break.
- **Error messages must be actionable.** Log the context needed to reproduce and diagnose the problem. Include relevant IDs, input shapes, and state at the point of failure.
- **Do not abuse try/catch as control flow.** Exceptions are for exceptional conditions. Predictable failure states (e.g., "record not found") must be handled with explicit conditional logic, not caught exceptions.
- **Distinguish between recoverable and unrecoverable errors.** A transient network timeout is recoverable. A schema violation on startup is not. Handle each class appropriately.
- **Fail fast on configuration errors.** Invalid environment variables, missing required configuration, and incompatible dependency versions must cause an immediate, loud failure at startup — not a silent degradation at runtime.

---

## 5. Performance Awareness

- **Understand the complexity of what you write.** Before submitting any loop, query, or data transformation, reason about its time and space complexity. Document it if it is non-trivial.
- **Prevent N+1 query patterns.** Database calls inside loops are forbidden unless explicitly justified. Batch, join, or eager-load as appropriate for the data layer in use.
- **Avoid blocking the event loop or main thread.** In async environments (Node.js, async Python, etc.), long-running synchronous operations must be offloaded. In threaded environments, shared state must be minimized and synchronization must be deliberate.
- **Do not over-fetch.** Query only the columns, fields, and records needed. Avoid `SELECT *` in production queries. Avoid loading full collections when a count or existence check suffices.
- **Cache deliberately, not reflexively.** Caching introduces consistency risk. Only cache when there is a measurable performance justification and when the invalidation strategy is defined.
- **Benchmark before optimizing.** Do not optimize code that has not been measured. Premature optimization that sacrifices clarity is a defect, not an improvement.

---

## 6. Security Practices

- **Secrets are never hardcoded.** API keys, passwords, tokens, connection strings, and credentials of any kind must be sourced from environment variables or a secrets manager. They must never appear in source code, commit history, or log output.
- **All user-supplied input must be validated and sanitized** before use in queries, commands, templates, or external calls. Assume all input is adversarial.
- **Prevent injection attacks.** Use parameterized queries or prepared statements for all database interactions. Never construct queries by string concatenation with user input. Apply equivalent discipline to shell commands, template rendering, and XML/HTML generation.
- **Apply the principle of least privilege.** Request only the permissions your code needs. Assign only the permissions an entity needs. Scope tokens and credentials as narrowly as possible.
- **Do not log sensitive data.** Personally identifiable information (PII), authentication tokens, payment data, and secrets must never appear in log output.
- **Validate on the server side.** Client-side validation is a UX convenience. It is not a security control. All validation that matters must occur server-side.
- **Be explicit about trust boundaries.** Know which data is trusted (internal system data) and which is untrusted (user input, third-party responses, environment variables). Treat untrusted data accordingly at every point it crosses a trust boundary.
- **Avoid unsafe deserialization.** Do not deserialize data from untrusted sources into executable or privileged object types without explicit schema validation.

---

## 7. Testing Requirements

- **Code is not complete without a validation strategy.** Every feature or change must be accompanied by either: automated tests, a documented manual test plan, or an explicit justification for why neither is applicable.
- **Unit tests are the default.** Pure functions, utility modules, business logic, and data transformations must have unit tests covering happy paths, edge cases, and failure cases.
- **Integration tests are required for system boundaries.** Code that interacts with databases, external APIs, message queues, or the filesystem must have integration tests that verify the interaction, not just the logic around it.
- **Tests must be deterministic.** Flaky tests are defects. Tests that depend on system time, network availability, or random values without mocking are not acceptable.
- **Tests must be readable.** A test is documentation. Its intent must be clear from the test name and structure alone. Use the Arrange-Act-Assert pattern. One assertion focus per test.
- **Do not test implementation details.** Tests must verify behavior and outcomes, not internal method calls or private state. Tests that break on refactoring without a behavior change are poorly written.
- **Coverage is a floor, not a ceiling.** Minimum coverage thresholds must be met, but meeting them with low-quality tests is not compliance. Critical paths require complete coverage of known failure modes.

---

## 8. Observability & Debugging

- **Structured logging is mandatory for backend services.** Log in a machine-parseable format (e.g., JSON). Include a timestamp, severity level, correlation/request ID, and relevant context in every log entry.
- **Log at the right level.**
  - `DEBUG`: Detailed diagnostic information for development use only.
  - `INFO`: Normal system behavior and key lifecycle events.
  - `WARN`: Unexpected conditions that do not prevent operation but may indicate a problem.
  - `ERROR`: Failures that require attention and may impact users.
- **Instrument key operations.** Latency-sensitive paths, external calls, and background jobs must emit metrics or traces. This is not optional for services that run in production.
- **Correlation IDs must propagate.** In distributed systems, a trace or correlation ID must be present on all outbound requests and all log entries within a request's lifecycle.
- **Avoid black-box implementations.** Any logic that cannot be reasoned about from its inputs, outputs, and logs is a liability. If a system is doing something opaque, add observability.
- **Errors logged must include context.** Log the operation that failed, the inputs involved (sanitized of sensitive data), the error message, and a stack trace where applicable.

---

## 9. Documentation Standards

- **Explain "why", not "what".** The code explains what it does. Comments explain why a decision was made, why a specific approach was chosen, or why an obvious alternative was rejected.
- **Document non-obvious behavior.** Any logic that is subtle, counterintuitive, or domain-specific must have an explanation at the point of use.
- **Public interfaces must be documented.** All exported functions, classes, types, and modules must have documentation that describes: purpose, parameters, return values, and known failure modes.
- **Keep comments current.** A comment that contradicts the code is worse than no comment. When code changes, update its comments.
- **Do not comment out code.** Dead code must be deleted, not commented out. Version control preserves history. Commented-out code is noise.
- **Document architectural decisions.** When making a non-trivial design choice — a data structure selection, a concurrency model, a trade-off — document the decision and its rationale at a level that is visible to future engineers.

---

## 10. Git & Change Discipline

- **Each commit must represent one logical change.** Mixing formatting fixes, feature additions, and refactors in a single commit is prohibited. Commits must be atomic and independently reviewable.
- **Commit messages must be meaningful.** The subject line must describe what changed and why in one sentence. Use the imperative mood: "Add retry logic to payment processor" not "Added some retries".
- **Changes must be minimal and scoped.** Do not modify files, functions, or logic outside the scope of the assigned task. If an adjacent issue must be addressed, it belongs in a separate commit or pull request.
- **Backward compatibility must be preserved** unless a breaking change is explicitly authorized. Deprecate before removing. Communicate deprecations clearly.
- **Do not reformat code unrelated to your change.** Formatting changes inflate diffs and obscure meaningful modifications. If a file needs reformatting, do it in a dedicated commit.
- **Pull requests must be reviewable.** A PR that cannot be understood by a reviewer in a reasonable amount of time is too large. Decompose accordingly.

---

## 11. Dependency Management

- **Do not introduce new dependencies casually.** Every new dependency is a maintenance burden, a security surface, and a potential source of future breakage. Its inclusion must be justified.
- **Justify new dependencies explicitly.** For each new dependency, answer: What does it do? Why can't this be accomplished with the standard library or existing dependencies? What is its license? Is it actively maintained?
- **Prefer standard library implementations.** If the standard library provides a safe, readable solution, use it. Do not add a package to avoid three lines of code.
- **Pin dependency versions.** Use lockfiles. Do not rely on version ranges that permit silent upgrades. Upgrades must be deliberate and tested.
- **Audit dependencies for known vulnerabilities** before introducing them and as part of ongoing maintenance.
- **Remove unused dependencies.** Dead dependencies in package manifests are not neutral. They must be removed.

---

## 12. Execution Workflow

This is the required sequence of operations for every task. Do not skip steps.

1. **Understand the requirement fully** before writing any code. Read the specification, user story, or task description in its entirety.
2. **Identify ambiguities.** If any requirement is unclear, underspecified, or potentially contradictory, raise the question before proceeding. Do not make assumptions and code forward.
3. **Survey the existing codebase.** Understand what already exists that is relevant to the task. Identify reusable components, established patterns, and potential conflicts.
4. **Plan the implementation.** Determine the scope of changes, the modules affected, the test strategy, and the rollout considerations before writing a single line.
5. **Implement incrementally.** Build in small, verifiable steps. Do not write large blocks of untested code in a single pass.
6. **Validate continuously.** Run tests, linters, and type checkers as you build. Do not defer validation to the end.
7. **Review your own output.** Before declaring the task complete, re-read your changes as a code reviewer would. Check for violations of every section in this document.
8. **Document and communicate.** Ensure all changes are documented appropriately, commits are clean, and any deferred work or known limitations are surfaced explicitly.

---

## 13. Anti-Patterns to Avoid

The following patterns are explicitly prohibited:

- **Hardcoding values.** Configuration, thresholds, environment-specific values, and any value that might change belong in constants, configuration files, or environment variables — not inline in logic.
- **Overengineering.** Do not build abstractions, interfaces, or frameworks for problems that do not yet exist. YAGNI: You Aren't Gonna Need It.
- **Premature abstraction.** Abstract when duplication is real and the abstraction boundary is well-understood. Not before.
- **Copy-paste duplication.** Duplicated logic is a maintenance defect. Every time the original changes, the duplicate becomes a bug.
- **Ignoring edge cases.** Empty collections, null values, zero, negative numbers, very large inputs, concurrent access, and network failures are not exotic scenarios. They are expected conditions. Handle them.
- **Writing code without understanding context.** Do not implement a feature without understanding what it does, why it exists, how it fits into the system, and what can go wrong.
- **Boolean parameter flags.** Functions that accept a boolean to toggle behavior are a code smell. Split them into two functions with clear names.
- **God objects and god functions.** Any class that does everything or any function that handles every case is a design failure. Decompose.
- **Action at a distance.** Code that produces effects far from where it is invoked — via global state, shared mutable singletons, or implicit side effects — is prohibited.
- **Inconsistency with the existing codebase.** Do not introduce a new style, pattern, or convention that conflicts with the established norms of the codebase without explicit authorization.

---

## 14. Definition of Done

A task is complete only when **all** of the following are true:

- [ ] **The code compiles and runs** without errors, warnings (where warnings are treated as errors), or type violations.
- [ ] **All requirements are met exactly.** Not approximately. Not with known gaps. Exactly.
- [ ] **Edge cases are handled.** Null inputs, empty states, boundary values, and failure conditions are accounted for.
- [ ] **Errors are handled explicitly.** No silent failures, no unhandled promise rejections, no unhandled exceptions in production paths.
- [ ] **The code is readable and maintainable.** Naming is clear, logic is flat, and the intent is obvious without requiring the reader to hold the entire system in their head.
- [ ] **The code is testable** and tests exist or a test strategy is documented.
- [ ] **No dead code, commented-out blocks, or debug artifacts** remain.
- [ ] **No secrets, credentials, or sensitive values** are present in the code or commit history.
- [ ] **Documentation is in place** for public interfaces, complex logic, and non-obvious decisions.
- [ ] **Changes are scoped and minimal.** No unrelated modifications are included.
- [ ] **The change is backward compatible** or the breaking change has been explicitly authorized and communicated.
- [ ] **Logging and observability are in place** for any new system boundary or critical path introduced.

If any item above cannot be checked off, the task is not done. Stop. Resolve the gap before marking it complete.

---

## 15. Frontend Code Style (React, TypeScript, Vite, Tailwind)

- **Functional Components & Hooks:** Use functional components and hooks. Avoid class components.
- **Naming Conventions:**
  - Folders/Files: `kebab-case` (e.g., `user-profile.tsx`) or `PascalCase` for component files depending on established repository convention.
  - Components: `PascalCase` (e.g., `UserProfile.tsx`).
  - Variables/Functions/Hooks: `camelCase` (e.g., `fetchData`, `useAuth`, `isLoggedIn`).
- **TypeScript:** Use explicit typings for props, state, and function return values. Avoid `any`.
- **Tailwind CSS:** 
  - Construct utility classes completely (do not concatenate strings dynamically for classes, as Tailwind won't detect them).
  - Use `clsx` and `tailwind-merge` (typically via a `cn` utility) for conditional class application.
- **Component Limits:** Adhere strictly to the Single Responsibility Principle. If a component grows too large (~200 lines), break it down.

---

## 16. Backend Code Style (Python, FastAPI, SQLAlchemy, Ruff)

- **Formatting:** Code must be formatted using **Ruff**. Do not debate formatting rules; rely on Ruff's uncompromising defaults (typically an 88-character line limit).
- **Type Hinting:** Use strict Python type hints everywhere. FastAPI relies on them for request validation and Pydantic schema generation.
- **Async Processing:** Since FastAPI is an asynchronous framework, use `async`/`await` for I/O bound operations. Use `AsyncSession` for SQLAlchemy interactions.
- **Layered Architecture:** 
  - Keep database models (`SQLAlchemy`) separate from data validation models (`Pydantic`).
  - Use FastAPI's Dependency Injection (`Depends()`) for managing database sessions and external services.
- **Alembic Restrictions:** Do not modify database schemas manually. Use Alembic for all schema migrations.

---

*This document is the contract between this codebase and any agent working within it. It is not a suggestion. It is the standard.*
