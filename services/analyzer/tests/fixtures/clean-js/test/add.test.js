"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { add } = require("../index.js");

test("adds numbers", () => {
  assert.strictEqual(add(2, 3), 5);
});
