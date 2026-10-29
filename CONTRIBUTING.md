# Contributing to Constructor

Thank you for your interest in contributing to Constructor!

Please refer to the [conda contributing guide](https://docs.conda.io/projects/conda/en/latest/dev-guide/contributing.html) for general guidelines on how to contribute to conda projects.
Using generative AI is generally allowed, but must follow `conda`'s [generative AI
policy](https://docs.conda.io/projects/conda/en/latest/dev-guide/contributing.html#generative-ai).


For Constructor-specific questions or issues, please open an issue on the [issue tracker](https://github.com/conda/constructor/issues) or start a discussion.

Please also review our [Code of Conduct](https://github.com/conda/constructor/blob/main/CODE_OF_CONDUCT.md) before contributing.

## Updating the change log

Each pull request requires a news file based on a [news file template](news/TEMPLATE).
Please follow the following conventions when creating the file:

- Use the issue number (not the PR number unless no issue is available), plus a short slug for the
  news file name. For example, `12345-remove-conda-utils-unix-path-to-win`.
- Use imperative mood (Add, Fix, Mark, Remove) when writing a news file item.
- End each bullet with a GitHub reference in parentheses.
  Prefer an issue when there is one, e.g., `(#12345)`, or `(#12345 via #12346)` to include a PR number.
  Several issues/PRs can be mentioned in the same parentheses; use commas to separate them.
