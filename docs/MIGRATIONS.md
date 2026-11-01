# Compatible migration procedure

001 is an additive bootstrap from the official empty starter. schema.sql is generated from boards.infrastructure.schema.TABLES and matches migration 001. It creates nineteen ab_* tables and supported indexes. Existing starter tables are left intact. No old profile is linked by email, and no old data is dropped.

The image entry point executes boards.infrastructure.migrate before uvicorn. DDL can be retried safely; required columns are verified even if a table already exists. A schema_versions marker is written only after verification. Concurrent marker conflicts retry. A failed setup prevents application startup.

For a future migration:

1. Save the numbered SQL file under migrations and add the ordered migration step to the runner.
2. Add nullable/default-compatible columns explicitly with ALTER TABLE. Do not rename/drop existing columns in a rolling deployment.
3. Backfill through authorized administrative tooling, validate counts and relationships, then switch reads/writes in a later compatible release.
4. Test from both an existing version and an empty final schema. Keep schema.sql complete for future remixes.
5. Back up before migration and retain the previous successful image. Roll back code without destructive schema reversal.

If an existing starter bucket contains valuable records, stop automatic identity migration. Prepare a separate reviewed import mapping each old profile to a genuine pool/subject and reconciling workspace roles. This release intentionally does not guess those mappings.
