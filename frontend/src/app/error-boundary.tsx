import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Unhandled application error:', error, info.componentStack)
  }

  override render() {
    if (this.state.error) {
      return (
        <div className="mx-auto flex max-w-xl flex-col items-center gap-4 px-4 py-24 text-center">
          <h1 className="text-h1 text-text-primary">Something went wrong</h1>
          <p className="text-lg text-text-secondary">
            Please reload the page. If the problem continues, try again later.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="h-13 rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
          >
            Reload
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
