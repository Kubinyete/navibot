#!/bin/bash

sed -E 's/"(token|key)": *"[a-zA-Z0-9_\.-]+"/"\1": "TOKEN_OR_API_KEY"/g' < release/config.json > config.json
