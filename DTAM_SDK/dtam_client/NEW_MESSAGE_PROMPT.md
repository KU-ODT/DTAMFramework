# Adding A DTAM Message

`dtam_client` is the SDK source of truth. `message` is only a user-side payload
generation workspace.

For a new message `XXXX_name`:

1. Add schema validation in `dtam_client/schema/msg_XXXX.py`.
2. Add receive parsing in `dtam_client/receiver/XXXX_name.py`.
3. Add a public send function in `dtam_client/msg/mXXXX.py`.
4. Register exports in `dtam_client/msg/__init__.py` and `dtam_client/__init__.py`.
5. Add the route in `dtam_client/_router.py`.
6. Add a valid sample payload in `dtam_client/samples.py`.
7. Add ICD markdown under `dtam_client/icd/KOR` and `dtam_client/icd/ENG`.
8. If the emulator needs random sample generation, add only a payload generator
   under `message/generator/XXXX_name.py`; import schema constants from
   `dtam_client.schema.msg_XXXX`.
9. Register the message in `app/registry.py` and `app/messages.py`.

Rules:

- `dtam_client/schema` is the only schema source.
- `dtam_client/receiver` is the only receive parser source.
- `dtam_client/msg` is the only socket sender source.
- `message/generator` must not open sockets or define protocol behavior.
- Every sample/generator should pass its matching `validate_message()` check.
