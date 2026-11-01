import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X, LayoutGrid, LoaderCircle } from 'lucide-react'
import { branding } from './branding'
export const palette = ['indigo', 'blue', 'teal', 'green', 'amber', 'orange', 'rose', 'purple', 'slate']
export function Brand() {
  return (
    <span className="brand">
      <svg className="brand-mark" viewBox="0 0 25 25" aria-hidden="true">
        <rect x="0" y="2" width="6" height="21" rx="2" fill="currentColor" />
        <rect x="9" y="4" width="6" height="16" rx="2" fill="currentColor" opacity=".75" />
        <rect x="18" y="6" width="6" height="11" rx="2" fill="currentColor" opacity=".45" />
      </svg>
      {branding.name}
      <span className="brand-dot">.</span>
    </span>
  )
}
export function Avatar({ name, size = 'normal' }: { name: string; size?: string }) {
  return (
    <span className={'avatar ' + size} title={name}>
      {name
        .split(/[ @]/)
        .filter(Boolean)
        .slice(0, 2)
        .map((n) => n[0])
        .join('')
        .toUpperCase()}
    </span>
  )
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <LayoutGrid size={26} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  )
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={24} /> Loading your workspace…
    </div>
  )
}
export function Dialog({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement
    ref.current?.showModal()
    return () => {
      ref.current?.close()
      previous?.focus()
    }
  }, [])
  return (
    <dialog
      className={wide ? 'dialog wide' : 'dialog'}
      ref={ref}
      aria-labelledby="dialog-title"
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <header>
        <h2 id="dialog-title">{title}</h2>
        <button className="icon-button" aria-label="Close dialog" onClick={onClose}>
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  )
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}
export function Toast({ message, error, onClose }: { message: string; error: boolean; onClose: () => void }) {
  const [host, setHost] = useState<HTMLElement>(document.body)
  useEffect(() => {
    // Native dialogs occupy the top layer. Keep feedback inside the active dialog
    // so its backdrop cannot hide errors and its focus trap includes dismissal.
    const update = () => {
      const dialogs = document.querySelectorAll<HTMLDialogElement>('dialog[open]')
      setHost(dialogs.item(dialogs.length - 1) || document.body)
    }
    update()
    const observer = new MutationObserver(update)
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['open'],
    })
    return () => observer.disconnect()
  }, [])
  return createPortal(
    <div className={'toast ' + (error ? 'error' : '')} role={error ? 'alert' : 'status'}>
      {message}
      <button className="icon-button" aria-label="Dismiss message" onClick={onClose}>
        <X size={16} />
      </button>
    </div>,
    host
  )
}
export function Due({ value, overdue = false }: { value: string | null; overdue?: boolean }) {
  if (!value) return null
  const formatted = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(
    new Date(value + 'T12:00:00')
  )
  return (
    <span className={overdue ? 'due overdue' : 'due'}>
      {formatted}
      {overdue ? ' · Overdue' : ''}
    </span>
  )
}
export function dateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}
export function actionLabel(action: string) {
  return action.replaceAll('_', ' ')
}
