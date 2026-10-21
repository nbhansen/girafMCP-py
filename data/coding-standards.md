# GIRAF Coding & Review Standards

Single source of truth for "how GIRAF code should be built." Maintained here so it lives in
one committed place (the `CLAUDE.md` files are local-only and never pushed to GitHub). The AI
PR reviewer's prompt is a distilled snapshot of this document; students read the same rules
during onboarding. Update this file each semester and regenerate the reviewer prompts from it.

> **Audience:** junior students (new each semester). Rules are explained so the review and the
> onboarding both *teach*, not just gate.

---

## 1. Platform architecture rules (all repos)

- **Shared concepts belong in `giraf-core`.** Users, organisations, citizens, grades,
  pictograms, and JWT auth are owned by `giraf-core` (Django + Ninja). App backends
  (weekplanner, VTA, foodplanner) only manage their *own* domain entities. A PR that
  re-implements a shared concept inside an app backend is a design smell — flag it.
- **Auth model:** `giraf-core` issues JWTs containing `org_roles` claims
  (`{"org_roles": {"1": "owner", "5": "member"}}`). Each app backend validates tokens locally
  with a shared `JWT_SECRET`. Role hierarchy: `owner > admin > member`. Never trust client
  role input; always derive authorisation from the validated token.
- **Target users & device:** autistic children with minimal/no verbal communication, plus
  caregivers and administrators. Flutter apps target **iPad/iPhone in landscape**. UI work that
  assumes portrait or desktop layout is a bug for this project.

## 2. What a good pull request looks like

- **Conventional Commits** for title/commits: `feat: …`, `fix: …`, `docs: …`, `chore: …`.
- **Branch naming:** `feat/123-description`, `fix/123-description`, `docs/…`, `chore/…`.
- **Description** explains *what* changed and *why* clearly enough that a reviewer who didn't
  write the code can understand the change without reading every line. Links the related issue.
- **Surgical scope:** the diff does one thing. Drive-by refactors, reformatting unrelated
  files, or unrelated dependency bumps mixed into a feature PR should be split out.
- **Tests** accompany behavioural changes.

## 3. Dart & Flutter rules (weekplanner, VTA, foodplanner)

Authoritative sources: Effective Dart, Flutter Architecture Guide, bloclibrary.dev. Don't guess
APIs — check the source.

### Naming
| Element | Convention |
|---|---|
| Classes, enums, typedefs, extensions | `UpperCamelCase` |
| Files, dirs, packages | `snake_case` |
| Variables, params, functions, constants | `lowerCamelCase` |

No `SCREAMING_CAPS`, no Hungarian notation. Acronyms >2 letters capitalise as words: `Http`, `Json`.

### Null safety
- `??` for defaults, `?.` for optional chaining, pattern matching for promotion.
- **Never use `!`** unless null is provably impossible — and then comment why.
- Don't initialise nullable variables to `null` explicitly.

### Widgets
- Default to `StatelessWidget`; use `StatefulWidget` only for genuine ephemeral local state
  (animation/text controllers, form state).
- `const` constructors everywhere possible; `const` instantiations when args are compile-time.
- **Dispose** every controller, subscription, listener, focus node in `dispose()`;
  `super.dispose()` last.
- After any `await` in a `State`, check `if (!mounted) return;` before `setState()`.
- Use `Theme.of(context)` for colours/text styles — never hardcode. Use
  `colorScheme.secondary`, not the deprecated `accentColor`.
- **Don't split widgets into private helper methods** (`_buildHeader()`). Extract to a
  separate `StatelessWidget` class instead.
- Don't store `BuildContext` in a field or pass it to services/repositories.
- Don't put business logic, API calls, or data transformation inside widget classes.
- Don't nest `ListView`/`GridView` in `Column`/`Row` without `Expanded`/`SizedBox`.
- Don't nest `Scaffold` in `Scaffold`.

### Deprecated APIs (reject)
`FlatButton`/`RaisedButton` → `TextButton`/`ElevatedButton`; `WillPopScope` → `PopScope`;
`MaterialStateProperty` → `WidgetStateProperty`; never use `new`.

### SOLID — scaled to project size (YAGNI)
- **Single Responsibility is the one that always applies.** Widgets do UI, BLoCs/Cubits do
  state, repositories do data. Keep `build()` focused.
- **Do not push juniors toward overengineering.** OCP/LSP/ISP/DIP matter at boundaries, but a
  2-screen app does **not** need full clean architecture with use cases and mappers. Don't
  create interfaces unless there are 2+ implementations or a test needs to mock. Three similar
  lines beat a premature abstraction.
- Constructor injection for dependencies; don't instantiate dependencies internally.

### State management
- `setState()` only for ephemeral single-widget state. State classes immutable, `final` fields,
  `copyWith()` for changes, Equatable/freezed for equality.
- BLoC: events past-tense (`LoginSubmitted`), states nouns (`LoginLoading`). One BLoC per
  feature. Never import Flutter in bloc files. `BlocListener` for side effects, `BlocBuilder`
  for UI.

### Generated & boilerplate code
- Generated API clients (e.g. foodplanner's `lib/api/openapi/**`), `*.g.dart`, `*.freezed.dart`
  are **not** reviewed for style — they're machine output.

## 4. Division of labour: linters vs. AI review

Linters/formatters/tests (`flutter analyze`, `dart format`, `flutter test`, ruff, mypy,
`dotnet format`) own formatting, naming nits, unused imports, type errors, and test failures.
The **AI reviewer does not duplicate those** — it reviews what static tools cannot see:
architecture/SRP, security, subtle logic bugs, and out-of-scope changes.
