import { useState } from 'react'
import type { AdminUser } from '../api/admin'
import { AdminGate, TempPasswordNotice } from '../components/admin/shared'
import { UserForm } from '../components/admin/UserForm'
import { UserTable } from '../components/admin/UserTable'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useAdminUsers } from '../hooks/useAdmin'

interface Issued {
  title: string
  email: string
  password: string
}

// Quản lý tài khoản (Admin): tạo, sửa, đặt lại mật khẩu, khoá / mở khoá. Tài khoản không bị xoá vì
// điểm và nhật ký còn tham chiếu tới người dùng (D-096). Mật khẩu tạm chỉ hiện một lần (D-097).
export default function AdminUsersPage() {
  const users = useAdminUsers()
  const [issued, setIssued] = useState<Issued | null>(null)
  const [editing, setEditing] = useState<AdminUser | null>(null)

  return (
    <AdminGate>
      {(admin) => (
        <>
          <PageTitle
            title="Tài khoản"
            subtitle="Giáo viên, Ban giám hiệu và quản trị viên. Giáo viên chủ nhiệm và giáo viên bộ môn được xác định theo phân công, không phải theo loại tài khoản."
          />
          {issued && (
            <TempPasswordNotice
              title={issued.title}
              email={issued.email}
              password={issued.password}
              onDone={() => setIssued(null)}
            />
          )}
          {editing && (
            <Panel id="sua-tai-khoan" title={`Sửa tài khoản: ${editing.full_name}`}>
              <UserForm
                key={editing.id}
                mode="edit"
                user={editing}
                isSelf={editing.id === admin.id}
                onDone={() => setEditing(null)}
              />
            </Panel>
          )}
          <Panel id="danh-sach-tai-khoan" title="Danh sách tài khoản">
            <QueryState query={users}>
              {(data) => (
                <UserTable
                  users={data}
                  selfId={admin.id}
                  onEdit={(user) => {
                    setIssued(null)
                    setEditing(user)
                  }}
                  onPasswordIssued={(user, password) => {
                    setEditing(null)
                    setIssued({
                      title: 'Mật khẩu tạm mới',
                      email: user.email,
                      password,
                    })
                  }}
                />
              )}
            </QueryState>
          </Panel>
          <Panel
            id="them-tai-khoan"
            title="Thêm tài khoản"
            description="Sau khi tạo, hệ thống hiện mật khẩu tạm một lần để bạn đưa cho người dùng."
          >
            <UserForm
              mode="create"
              onCreated={(created) => {
                setEditing(null)
                setIssued({
                  title: 'Đã tạo tài khoản',
                  email: created.user.email,
                  password: created.temporary_password,
                })
              }}
            />
          </Panel>
        </>
      )}
    </AdminGate>
  )
}
