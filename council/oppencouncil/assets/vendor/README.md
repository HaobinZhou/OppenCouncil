# Browser dependency

- markdown-it 15.0.2 (MIT): https://github.com/markdown-it/markdown-it
- Download: https://registry.npmjs.org/markdown-it/-/markdown-it-15.0.2.tgz
- npm tarball integrity: `sha512-q4IGxMv56jCqT4OCRCADBoDP3LO4MhmTXjFbphHPXs4g3j9Xg5RDnxqN8IF/3vIWEU+VCnUq+7JUg/cfy2E6Qw==`
- Bundle: unmodified `dist/browser/markdown-it.umd.min.js`, renamed `markdown-it.min.js`; license included beside it.
- Served locally, with no runtime CDN dependency. Configuration is in `../markdown.js`.

When updating, pin an explicit version, verify the registry integrity before extracting, retain its license, and rerun the Markdown security and lifecycle tests. Upstream safety guidance: https://github.com/markdown-it/markdown-it/blob/master/docs/safety.md
