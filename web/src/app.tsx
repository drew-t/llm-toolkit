import { Route, Switch } from 'wouter-preact'
import { AppShell } from './components/AppShell'
import { HostsPage } from './pages/HostsPage'
import { ModelsPage } from './pages/ModelsPage'
import { ResultsPage } from './pages/ResultsPage'
import { RunPage } from './pages/RunPage'

export function App() {
  return (
    <AppShell>
      <Switch>
        <Route path="/" component={ResultsPage} />
        <Route path="/hosts" component={HostsPage} />
        <Route path="/run" component={RunPage} />
        <Route path="/models" component={ModelsPage} />
        <Route>
          <div class="p-6 text-text-muted">Page not found.</div>
        </Route>
      </Switch>
    </AppShell>
  )
}
