"use client";

import { useState } from "react";
import { APP_NAME, APP_VERSION, APP_TAGLINE } from "@/lib/constants";
import { repository } from "@/lib/repository";
import { useAppStore } from "@/lib/store";
import { useDesktop } from "@/hooks/use-desktop";
import { PageContainer, PageHeader, MetaRow } from "@/components/shared/page";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function Row({
  title,
  description,
  control,
}: {
  title: string;
  description: string;
  control: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-w-2xl divide-y divide-border rounded-lg border border-border bg-card px-5">
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const user = repository.currentUser;
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const setWorkspace = useAppStore((s) => s.setWorkspace);
  const { isDesktop, version, platform } = useDesktop();
  const [dense, setDense] = useState(true);
  const [notif, setNotif] = useState(true);
  const [approvalNotif, setApprovalNotif] = useState(true);

  const providers = [
    { name: "Primary reasoning", value: "Configured" },
    { name: "Fast routing", value: "Configured" },
    { name: "Verification", value: "Configured" },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        description="Configure AutoFlow. All settings in this build are local."
      />

      <Tabs defaultValue="general">
        <TabsList className="flex-wrap">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="workspace">Workspace</TabsTrigger>
          <TabsTrigger value="providers">Model Providers</TabsTrigger>
          <TabsTrigger value="automation">Automation</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="about">About</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Panel>
            <div className="py-4">
              <Label htmlFor="name">Display name</Label>
              <Input id="name" defaultValue={user.name} className="mt-1.5 max-w-sm" />
            </div>
            <div className="py-4">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                defaultValue={user.email}
                className="mt-1.5 max-w-sm"
              />
            </div>
            <Row
              title="Role"
              description="Determines what you can approve and configure."
              control={
                <span className="rounded-md border border-border px-2 py-0.5 text-sm">
                  {user.role}
                </span>
              }
            />
          </Panel>
        </TabsContent>

        <TabsContent value="appearance">
          <Panel>
            <Row
              title="Theme"
              description="Monochrome is the only supported theme in this build."
              control={
                <span className="rounded-md border border-border px-2 py-0.5 text-sm">
                  Monochrome
                </span>
              }
            />
            <Row
              title="Dense layout"
              description="Increase information density across tables and lists."
              control={<Switch checked={dense} onCheckedChange={setDense} />}
            />
          </Panel>
        </TabsContent>

        <TabsContent value="workspace">
          <Panel>
            <div className="py-4">
              <Label>Active workspace</Label>
              <Select value={activeWs} onValueChange={setWorkspace}>
                <SelectTrigger className="mt-1.5 max-w-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {repository.workspaces().map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {repository.workspace(activeWs) && (
              <Row
                title="Members"
                description="People with access to this workspace."
                control={
                  <span className="text-sm tabular">
                    {repository.workspace(activeWs)!.members}
                  </span>
                }
              />
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="providers">
          <Panel>
            {providers.map((p) => (
              <Row
                key={p.name}
                title={p.name}
                description="Provider credentials are held outside the desktop client."
                control={
                  <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
                    {p.value}
                  </span>
                }
              />
            ))}
          </Panel>
        </TabsContent>

        <TabsContent value="automation">
          <Panel>
            <Row
              title="Require approval for external actions"
              description="AutoFlow always asks before sending or publishing."
              control={<Switch checked disabled />}
            />
            <Row
              title="Auto-retry on recovery"
              description="Attempt safe recovery before failing a step."
              control={<Switch defaultChecked />}
            />
            <Row
              title="Max recovery attempts"
              description="Attempts before a step fails safely."
              control={
                <Input
                  type="number"
                  defaultValue={3}
                  className="h-8 w-16 text-center"
                />
              }
            />
          </Panel>
        </TabsContent>

        <TabsContent value="notifications">
          <Panel>
            <Row
              title="Execution updates"
              description="Notify when a task changes state."
              control={<Switch checked={notif} onCheckedChange={setNotif} />}
            />
            <Row
              title="Approval requests"
              description="Notify when a decision is required."
              control={
                <Switch
                  checked={approvalNotif}
                  onCheckedChange={setApprovalNotif}
                />
              }
            />
          </Panel>
        </TabsContent>

        <TabsContent value="security">
          <Panel>
            <Row
              title="Renderer isolation"
              description="The interface has no direct Node.js or filesystem access."
              control={
                <span className="rounded-md border border-border px-2 py-0.5 text-xs">
                  Enabled
                </span>
              }
            />
            <Row
              title="Context isolation"
              description="Preload exposes only a narrow, explicit API."
              control={
                <span className="rounded-md border border-border px-2 py-0.5 text-xs">
                  Enabled
                </span>
              }
            />
            <Row
              title="External links"
              description="Open outside the app window in your browser."
              control={
                <span className="rounded-md border border-border px-2 py-0.5 text-xs">
                  System browser
                </span>
              }
            />
          </Panel>
        </TabsContent>

        <TabsContent value="about">
          <Panel>
            <div className="py-4">
              <MetaRow label="Product">{APP_NAME}</MetaRow>
              <MetaRow label="Tagline">{APP_TAGLINE}</MetaRow>
              <MetaRow label="Version" mono>
                {version ?? APP_VERSION}
              </MetaRow>
              <MetaRow label="Runtime">
                {isDesktop ? "Electron desktop" : "Browser (dev)"}
              </MetaRow>
              {platform && (
                <MetaRow label="Platform" mono>
                  {platform}
                </MetaRow>
              )}
            </div>
            <div className="py-4">
              <Button variant="outline" size="sm">
                Check for updates
              </Button>
            </div>
          </Panel>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
