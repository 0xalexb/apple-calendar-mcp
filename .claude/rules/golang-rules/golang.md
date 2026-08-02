---
paths:
  - "**/*.go"
---

# Go Rules

## Code Style

- Add an empty line before `return`, `continue`, and `break` statements.
- Do not write comments when the code is self-explanatory.
- End comments with a period.
- Use `errors.New` for new sentinel or static errors. Use `fmt.Errorf` with `%w` only for wrapping existing errors. Never use `fmt.Errorf` to construct error messages without wrapping.
- Avoid inline error handling: do not use `if err := ...; err != nil`.
- Never precede `if` conditions with an assignment statement.
- Never use `math/rand` or `math/rand/v2`. Always use `crypto/rand`.
- Use `http.NoBody` instead of `nil` for empty request bodies.
- Never use `github.com/google/uuid`. Always use `github.com/gofrs/uuid/v5`.
- Place unexported methods after exported ones in each file.
- Use `github.com/shopspring/decimal` (`decimal.Decimal`) instead of `float64` for decimal numbers.
- Always check the boolean result of type assertions.
- Never create global or package-level variables except for `fx.Module`, reusable constants, enums, and sentinel errors.
- Prefer positive conditions in `if` statements. Avoid negation when the positive form is clearer.
- Avoid returning more than 2 values from functions.
- Never create `init()` functions.
- Never concatinate strings with `+` in sql queries.
- Improve readability of repository functions with starting with sql queries.
- Use 'pgx.Collect...' functions to collect query results into slices, maps and structs.

## Linters

- When there is excessive use of `nolint` directives, consider adjusting the linter configuration instead.

## Dependency Injection (Uber Fx)

- Each package has its own `di.go` file.
- A DI module groups all DI modules of its immediate subpackages.
- Keep DI module creation separate from application logic.
- Use a struct with `fx.In` to inject more than 2 dependencies into a constructor.
- Name the `fx.In` struct as `{TargetStruct}Params` and place it next to the target struct.
- Do not create DI modules in `main.go`. Define modules in the package where the logic lives. Importing modules from other packages is fine.

## Tests

- Always use `t.Parallel()` in tests.
- One test file per source file: `{file_name}_test.go`.

## Logging

- Use the global `log/slog` package for all logging.
- Never pass a logger as a function parameter. Use global `slog` functions: `slog.Info`, `slog.Error`, `slog.Warn`, `slog.Debug`.
- Never call `slog.Default()`. Use global `slog` functions directly.

## HTTP

- Use the standard library `net/http` router.
- Use `github.com/go-pkgz/routegroup` for grouping routes and middlewares.

## Version

- The current Go version is 1.25.
