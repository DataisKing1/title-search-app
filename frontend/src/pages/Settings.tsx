import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { User, Lock, Bell, Shield } from 'lucide-react'

export default function Settings() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'notifications'>('profile')

  // Password change form
  const [passwordForm, setPasswordForm] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  })

  const changePasswordMutation = useMutation({
    mutationFn: () => authApi.changePassword(passwordForm.old_password, passwordForm.new_password),
    onSuccess: () => {
      toast.success('Password changed successfully!')
      setPasswordForm({ old_password: '', new_password: '', confirm_password: '' })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to change password')
    },
  })

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault()
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error('New passwords do not match')
      return
    }
    if (passwordForm.new_password.length < 12) {
      toast.error('Password must be at least 12 characters')
      return
    }
    changePasswordMutation.mutate()
  }

  const tabs = [
    { id: 'profile', name: 'Profile', icon: User },
    { id: 'security', name: 'Security', icon: Lock },
    { id: 'notifications', name: 'Notifications', icon: Bell },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <nav className="w-48 flex-shrink-0">
          <ul className="space-y-1">
            {tabs.map((tab) => (
              <li key={tab.id}>
                <button
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
                    activeTab === tab.id
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <tab.icon className="h-5 w-5" />
                  {tab.name}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Profile Information
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    disabled
                    className="input bg-gray-50"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Email cannot be changed
                  </p>
                </div>

                <div>
                  <label className="label">Full Name</label>
                  <input
                    type="text"
                    value={user?.full_name || ''}
                    className="input"
                    placeholder="Enter your full name"
                    readOnly
                  />
                </div>

                <div>
                  <label className="label">Account Type</label>
                  <div className="flex items-center gap-2">
                    <Shield className={`h-5 w-5 ${user?.is_admin ? 'text-primary-600' : 'text-gray-400'}`} />
                    <span className="text-sm font-medium">
                      {user?.is_admin ? 'Administrator' : 'Standard User'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Change Password
              </h2>

              <form onSubmit={handlePasswordChange} className="space-y-4 max-w-md">
                <div>
                  <label className="label">Current Password</label>
                  <input
                    type="password"
                    value={passwordForm.old_password}
                    onChange={(e) =>
                      setPasswordForm((prev) => ({
                        ...prev,
                        old_password: e.target.value,
                      }))
                    }
                    required
                    className="input"
                    placeholder="Enter current password"
                  />
                </div>

                <div>
                  <label className="label">New Password</label>
                  <input
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(e) =>
                      setPasswordForm((prev) => ({
                        ...prev,
                        new_password: e.target.value,
                      }))
                    }
                    required
                    minLength={12}
                    className="input"
                    placeholder="Enter new password (min 12 characters)"
                  />
                </div>

                <div>
                  <label className="label">Confirm New Password</label>
                  <input
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(e) =>
                      setPasswordForm((prev) => ({
                        ...prev,
                        confirm_password: e.target.value,
                      }))
                    }
                    required
                    className="input"
                    placeholder="Confirm new password"
                  />
                </div>

                <button
                  type="submit"
                  disabled={changePasswordMutation.isPending}
                  className="btn btn-primary disabled:opacity-50"
                >
                  {changePasswordMutation.isPending
                    ? 'Changing...'
                    : 'Change Password'}
                </button>
              </form>

              <div className="mt-6 pt-6 border-t">
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Password Requirements
                </h3>
                <ul className="text-sm text-gray-600 space-y-1">
                  <li>At least 12 characters long</li>
                  <li>Include uppercase and lowercase letters</li>
                  <li>Include at least one number</li>
                  <li>Include at least one special character</li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Notification Preferences
              </h2>

              <div className="space-y-4">
                <div className="flex items-center justify-between py-3 border-b">
                  <div>
                    <p className="font-medium text-gray-900">
                      Search Completed
                    </p>
                    <p className="text-sm text-gray-500">
                      Get notified when a title search is completed
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>

                <div className="flex items-center justify-between py-3 border-b">
                  <div>
                    <p className="font-medium text-gray-900">Search Failed</p>
                    <p className="text-sm text-gray-500">
                      Get notified when a title search fails
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>

                <div className="flex items-center justify-between py-3 border-b">
                  <div>
                    <p className="font-medium text-gray-900">Report Ready</p>
                    <p className="text-sm text-gray-500">
                      Get notified when a title report is ready
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>

                <div className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium text-gray-900">Batch Complete</p>
                    <p className="text-sm text-gray-500">
                      Get notified when batch processing completes
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </div>
              </div>

              <p className="mt-4 text-sm text-gray-500">
                Note: Email notifications require SMTP to be configured.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
