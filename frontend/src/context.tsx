import { createContext, useContext, type Dispatch, type SetStateAction } from 'react'
import type { Snapshot, User, Command, Card } from './types'
export type ModalState = {
  kind: 'board' | 'list' | 'card' | 'board-settings' | 'label' | 'invite' | 'activity' | 'ai' | 'dependencies'
  boardId?: string
  listId?: string
  labelId?: string
  aiKind?: 'summary' | 'recommendations'
}
export type WorkspaceContextValue = {
  snapshot: Snapshot
  user: User
  refresh: () => Promise<void>
  perform: <T = Record<string, unknown>>(command: Command, message?: string) => Promise<T | null>
  setSnapshot: Dispatch<SetStateAction<Snapshot | null>>
  openCard: (id: string) => void
  openModal: (modal: ModalState) => void
  navigate: (route: string) => void
  notify: (message: string, error?: boolean) => void
}
export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)
export function useWorkspace() {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('Workspace required')
  return value
}
export function eligibleMembers(snapshot: Snapshot, boardId: string) {
  const board = snapshot.boards.find((b) => b.id === boardId)
  const ids = new Set(snapshot.board_members.filter((m) => m.board_id === boardId).map((m) => m.user_id))
  return snapshot.members.filter(
    (m) => board?.visibility === 'workspace' || m.role === 'OWNER' || ids.has(m.id)
  )
}
