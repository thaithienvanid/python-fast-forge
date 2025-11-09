# Initial Schema Migration

This directory will contain Atlas migration files generated from your SQLAlchemy models.

## Generating the Initial Migration

Once you have Atlas CLI installed, generate the initial migration with:

```bash
# Make sure your database is empty or at the desired starting state
make migrate-create m="initial_schema"
```

This will generate SQL migration files based on your SQLAlchemy models in `src/domain/models/`.

## Migration File Format

Atlas migrations are plain SQL files with timestamps:

```
migrations/
├── 20251111120000_initial_schema.sql
├── 20251111130000_add_posts_table.sql
└── atlas.sum (checksum file for integrity)
```

## Quick Start

1. **Install Atlas CLI**:
   ```bash
   curl -sSf https://atlasgo.sh | sh
   # or: brew install ariga/tap/atlas
   ```

2. **Generate initial migration**:
   ```bash
   make migrate-create m="initial_schema"
   ```

3. **Apply migration**:
   ```bash
   make migrate
   ```

4. **Verify**:
   ```bash
   make migrate-status
   ```

## Documentation

- Setup guide: `ATLAS_SETUP.md` (root directory)
- Quick reference: `.atlas-quick-reference.md` (root directory)
- Official docs: https://atlasgo.io/

## Notes

- This directory should be committed to version control
- Atlas will create `atlas.sum` for migration integrity
- Never manually edit generated migration files
- Use `make migrate-create` to generate new migrations
