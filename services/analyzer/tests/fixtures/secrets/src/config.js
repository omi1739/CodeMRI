"use strict";

// Placeholder fixture content. The fake credential values used by the secret
// detection tests are written into a pytest tmp dir at runtime (see conftest.py)
// so no secret-shaped strings are committed to this repository.
const config = {
  awsAccessKeyId: "",
  githubToken: "",
  apiKey: "",
};

module.exports = { config };