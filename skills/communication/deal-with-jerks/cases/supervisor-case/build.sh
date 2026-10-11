#!/bin/bash
set -e
cat _base.html modules/*.html _footer.html > index.html
echo "Built index.html — open it in your browser."
