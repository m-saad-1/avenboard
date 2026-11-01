import { cpSync, mkdirSync } from 'node:fs'
mkdirSync('../app/boards/static', { recursive: true })
cpSync('dist', '../app/boards/static', { recursive: true })
