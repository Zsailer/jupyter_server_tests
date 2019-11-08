# Unit tests for Jupyter Server

![](https://github.com/Zsailer/jupyter_server_tests/workflows/Tests/badge.svg)

**This repo is only temporary**—the plan is to eventually merge this repo into [jupyter/jupyter_server](https://github.com/jupyter/jupyter_server)

These tests currently depend on [this branch](https://github.com/Zsailer/jupyter_server/tree/httpserver) of Jupyter Server.

The goal for this test suite is to leverage pytest's strengths. All tests should be explicit and follow standard pytest syntax. Writing a test for Jupyter Server should feel as simple as writing a typical pytest unit test.