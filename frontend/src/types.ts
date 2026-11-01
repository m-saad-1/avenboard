import type { paths, components } from './api.generated'
export type Command = paths['/api/commands']['post']['requestBody']['content']['application/json']
export type Role = 'OWNER' | 'MEMBER' | 'VIEWER'
export type User = components['schemas']['User']
export type Workspace = components['schemas']['Workspace']
export type Board = components['schemas']['Board']
export type Lane = components['schemas']['Lane']
export type Item = components['schemas']['Item']
export type Card = components['schemas']['Card']
export type Label = components['schemas']['Label']
export type Activity = components['schemas']['Activity']
export type Dependency = components['schemas']['DependencyRecord']
export type Invitation = components['schemas']['Invitation']
export type Snapshot = components['schemas']['Snapshot']
