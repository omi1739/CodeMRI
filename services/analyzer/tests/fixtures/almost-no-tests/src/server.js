const express = require("express");
const { users } = require("./users.js");

const app = express();
app.get("/users", (req, res) => res.json(users));
app.listen(3000);
