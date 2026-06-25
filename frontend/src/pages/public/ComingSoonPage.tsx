interface ComingSoonPageProps {
  title: string
}

/** Placeholder for routes whose layout/navigation already work but whose content lands in
 * a later milestone (see the Phase 4 foundation plan's "explicitly out of scope" list). */
export function ComingSoonPage({ title }: ComingSoonPageProps) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-20 text-center">
      <h1 className="text-h1 text-text-primary">{title}</h1>
      <p className="text-lg text-text-secondary">
        This page is part of the planned Phase 4 scope and is being built in an upcoming milestone.
      </p>
    </div>
  )
}
