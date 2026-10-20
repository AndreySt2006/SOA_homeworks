#!/bin/sh
set -e

mkdir -p app/generated
touch app/generated/__init__.py

datamodel-codegen \
  --input src/main/resources/openapi/openapi.yaml \
  --input-file-type openapi \
  --output app/generated/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections \
  --field-constraints

echo "Модели успешно сгенерированы!"