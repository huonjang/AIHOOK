import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { accountApi, type AccountProfile } from '../services/api'

type AuthState = {
  profile: AccountProfile | null
  loading: boolean
  onAuthenticated: (profile: AccountProfile) => void
  refreshProfile: () => Promise<void>
  signOut: () => Promise<void>
}
const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<AccountProfile | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    accountApi.me().then(user => { if (active) setProfile(user) }).catch(() => { if (active) setProfile(null) })
      .finally(() => { if (active) setLoading(false) })
    const unauthorized = () => { if (active) setProfile(null) }
    window.addEventListener('aihook:unauthorized', unauthorized)
    return () => { active = false; window.removeEventListener('aihook:unauthorized', unauthorized) }
  }, [])
  const signOut = async () => {
    try { await accountApi.logout() } finally { setProfile(null) }
  }
  const refreshProfile = async () => { setProfile(await accountApi.me()) }
  return <AuthContext.Provider value={{ profile, loading, onAuthenticated: setProfile, refreshProfile, signOut }}>
    {children}
  </AuthContext.Provider>
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth must be used inside AuthProvider')
  return state
}
