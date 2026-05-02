import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const ToastContext = createContext(null)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = Math.random().toString(36).slice(2, 9)
    setToasts((current) => [...current, { id, message, type }])

    if (duration > 0) {
      setTimeout(() => {
        setToasts((current) => current.filter((t) => t.id !== id))
      }, duration)
    }
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const contextValue = useMemo(
    () => ({
      success: (msg) => addToast(msg, 'success'),
      error: (msg) => addToast(msg, 'error'),
      info: (msg) => addToast(msg, 'info'),
      warn: (msg) => addToast(msg, 'warn'),
      remove: removeToast,
    }),
    [addToast, removeToast],
  )

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`} onClick={() => removeToast(toast.id)}>
            <div className="toast-content">{toast.message}</div>
            <button type="button" className="toast-close" onClick={(e) => { e.stopPropagation(); removeToast(toast.id); }}>
              &times;
            </button>
            <div className="toast-progress" />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
