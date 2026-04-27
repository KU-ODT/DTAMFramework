from pydantic import BaseModel, create_model, Field
import json

class MyConfig:
    json_schema_extra = {"example": {"role": "test", "payload": {}}}

Model = create_model("TestModel", __config__=MyConfig, role=(str, ...), payload=(dict, ...))
print(Model.model_json_schema() if hasattr(Model, 'model_json_schema') else Model.schema_json())
