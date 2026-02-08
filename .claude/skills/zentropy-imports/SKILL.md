---
name: zentropy-imports
description: |
  Import ordering conventions for Zentropy Scout. Load when:
  - Writing new Python or TypeScript files
  - Reviewing or fixing import order
  - Someone asks about "imports", "import order", or "ruff isort"
---

# Zentropy Scout Import Ordering

## Python Import Order

```python
# 1. Standard library
import asyncio
import json
from datetime import datetime
from typing import Optional

# 2. Third-party packages
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local imports (absolute)
from app.core.config import settings
from app.models.persona import Persona
from app.repositories.persona import PersonaRepository
from app.services.extraction import ExtractionService
```

**Enforcement:** `ruff` with isort rules in `pyproject.toml`

```toml
[tool.ruff.lint.isort]
known-first-party = ["app"]
```

## TypeScript Import Order

```typescript
// 1. React/Next.js
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// 2. Third-party
import { z } from 'zod';
import { useForm } from 'react-hook-form';

// 3. Local imports — components
import { Button } from '@/components/ui/button';
import { PersonaForm } from '@/components/persona/PersonaForm';

// 4. Local imports — hooks, utils, types
import { usePersona } from '@/hooks/usePersona';
import { formatDate } from '@/lib/utils';
import type { Persona } from '@/types';
```

## Quick Reference

| Language | Order |
|----------|-------|
| Python | stdlib → third-party → local |
| TypeScript | react/next → third-party → components → hooks/utils/types |

## Common Mistakes

```python
# WRONG: Mixed order
from app.models import Persona  # local
from pydantic import BaseModel  # third-party (should be before local)
import json                      # stdlib (should be first)

# CORRECT: Proper grouping
import json
from pydantic import BaseModel
from app.models import Persona
```
