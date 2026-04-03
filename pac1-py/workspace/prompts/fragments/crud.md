TASK TYPE: Simple CRUD operation.
- Verify the target file exists (or doesn't) before writing.
- A write response of "written: path (OK)" means SUCCESS — do NOT repeat the same write. Proceed to re-read for verification.
- After writing, re-read the file to confirm the write succeeded.
- Include the modified file in grounding_refs.
