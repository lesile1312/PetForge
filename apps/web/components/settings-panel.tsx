"use client";

import type { PetConfig } from "@petforge/pet-schema";
import type { CSSProperties } from "react";
import { Icon } from "@/components/icons";

type RangeStyle = CSSProperties & { "--range-progress": string };
const rangeStyle = (percent: number): RangeStyle => ({ "--range-progress": `${percent}%` });

interface SettingsPanelProps {
  config: PetConfig;
  onChange: (config: PetConfig) => void;
}

export function SettingsPanel({ config, onChange }: SettingsPanelProps) {
  function changeName(name: string) {
    onChange({ ...config, name });
  }

  function changeAppearance(scale: number) {
    onChange({ ...config, appearance: { ...config.appearance, scale } });
  }

  function changeBehavior(patch: Partial<PetConfig["behavior"]>) {
    onChange({ ...config, behavior: { ...config.behavior, ...patch } });
  }

  function changeWindow(patch: Partial<PetConfig["window"]>) {
    onChange({ ...config, window: { ...config.window, ...patch } });
  }

  return (
    <aside className="settings-panel" aria-label="桌宠设置">
      <div className="settings-heading"><div><span className="section-eyebrow">角色设置</span><h2>让它更像你</h2></div><span className="settings-save-dot" title="更改会在保存后同步" /></div>

      <div className="setting-group">
        <label className="setting-label" htmlFor="pet-name">桌宠名称</label>
        <div className="name-field"><span className="name-avatar"><Icon name="spark" size={15} /></span><input id="pet-name" value={config.name} maxLength={40} onChange={(event) => changeName(event.target.value)} placeholder="给它起个名字" /></div>
        <p className="field-help">这个名字会显示在桌面预览里</p>
      </div>

      <div className="setting-divider" />
      <div className="setting-group">
        <div className="setting-label-row"><label className="setting-label" htmlFor="pet-size">角色大小</label><output htmlFor="pet-size" className="range-output">{Math.round(config.appearance.scale * 100)}%</output></div>
        <input id="pet-size" className="range-control" type="range" min="50" max="200" step="5" value={Math.round(config.appearance.scale * 100)} style={rangeStyle(((config.appearance.scale - 0.5) / 1.5) * 100)} onChange={(event) => changeAppearance(Number(event.target.value) / 100)} />
        <div className="range-labels"><span>小巧</span><span>刚刚好</span><span>醒目</span></div>
      </div>

      <div className="setting-group">
        <div className="setting-label-row"><label className="setting-label" htmlFor="pet-speed">行走速度</label><output htmlFor="pet-speed" className="range-output">{config.behavior.moveSpeed} <small>px/s</small></output></div>
        <input id="pet-speed" className="range-control" type="range" min="20" max="300" step="10" value={config.behavior.moveSpeed} style={rangeStyle(((config.behavior.moveSpeed - 20) / 280) * 100)} onChange={(event) => changeBehavior({ moveSpeed: Number(event.target.value) })} />
        <div className="range-labels"><span>慢慢走</span><span>刚刚好</span><span>活泼点</span></div>
      </div>

      <div className="setting-group setting-group-tight">
        <div className="setting-label-row"><label className="setting-label" htmlFor="idle-duration">待机多久后睡觉</label><output htmlFor="idle-duration" className="range-output">{config.behavior.idleDuration} <small>秒</small></output></div>
        <input id="idle-duration" className="range-control" type="range" min="10" max="120" step="5" value={config.behavior.idleDuration} style={rangeStyle(((config.behavior.idleDuration - 10) / 110) * 100)} onChange={(event) => changeBehavior({ idleDuration: Number(event.target.value) })} />
        <div className="range-labels"><span>10 秒</span><span>1 分钟</span><span>2 分钟</span></div>
      </div>

      <div className="setting-group setting-group-tight">
        <div className="setting-label-row"><label className="setting-label" htmlFor="sleep-duration">休息时长</label><output htmlFor="sleep-duration" className="range-output">{config.behavior.sleepDuration} <small>秒</small></output></div>
        <input id="sleep-duration" className="range-control" type="range" min="30" max="600" step="30" value={config.behavior.sleepDuration} style={rangeStyle(((config.behavior.sleepDuration - 30) / 570) * 100)} onChange={(event) => changeBehavior({ sleepDuration: Number(event.target.value) })} />
        <div className="range-labels"><span>30 秒</span><span>5 分钟</span><span>10 分钟</span></div>
      </div>

      <div className="setting-group">
        <span className="setting-label">出现位置</span>
        <div className="segmented-control" role="group" aria-label="桌宠初始位置">
          {(["left", "right", "random"] as const).map((position) => (
            <button type="button" key={position} aria-pressed={config.behavior.initialPosition === position} onClick={() => changeBehavior({ initialPosition: position })}>
              {position === "left" ? "左下" : position === "right" ? "右下" : "随机"}
            </button>
          ))}
        </div>
      </div>

      <div className="setting-divider" />
      <div className="setting-group setting-group-tight">
        <div className="setting-label-row"><span className="setting-label">随机散步</span><span className="setting-summary">{config.behavior.randomWalkFrequency === "low" ? "偶尔" : config.behavior.randomWalkFrequency === "high" ? "常常" : "适中"}</span></div>
        <div className="frequency-options" role="group" aria-label="随机散步频率">
          {(["low", "medium", "high"] as const).map((frequency) => (
            <button type="button" key={frequency} className={config.behavior.randomWalkFrequency === frequency ? "is-selected" : ""} aria-pressed={config.behavior.randomWalkFrequency === frequency} onClick={() => changeBehavior({ randomWalkFrequency: frequency })}>
              <i className={`frequency-mark frequency-${frequency}`} /><span>{frequency === "low" ? "偶尔" : frequency === "medium" ? "适中" : "常常"}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="setting-group setting-group-tight toggle-list">
        <Toggle label="允许随机跳跃" detail="偶尔轻轻跳一下" icon="sun" checked={config.behavior.randomJump} onChange={(checked) => changeBehavior({ randomJump: checked })} />
        <Toggle label="自动进入睡眠" detail="安静时会休息一会儿" icon="moon" checked={config.behavior.autoSleep} onChange={(checked) => changeBehavior({ autoSleep: checked })} />
        <Toggle label="允许鼠标拖动" detail="抓住它，带它换个位置" icon="mouse" checked={config.behavior.draggable} onChange={(checked) => changeBehavior({ draggable: checked })} />
      </div>

      <div className="setting-divider" />
      <div className="setting-group setting-group-tight toggle-list">
        <Toggle label="始终显示在最前" detail="不被其他窗口遮住" icon="pin" checked={config.window.alwaysOnTop} onChange={(checked) => changeWindow({ alwaysOnTop: checked })} />
        <Toggle label="透明区域点击穿透" detail="只在角色上接收鼠标" icon="layers" checked={config.window.mousePassthrough} onChange={(checked) => changeWindow({ mousePassthrough: checked })} />
      </div>

      <div className="settings-note"><Icon name="spark" size={15} /><span>桌宠会根据你的设置随机行动，和它互动时会先回应你。</span></div>
    </aside>
  );
}

function Toggle({ label, detail, icon, checked, onChange }: { label: string; detail: string; icon: "sun" | "moon" | "mouse" | "pin" | "layers"; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="toggle-row">
      <span className="toggle-icon"><Icon name={icon} size={15} /></span>
      <span className="toggle-copy"><b>{label}</b><small>{detail}</small></span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-switch" aria-hidden="true"><i /></span>
    </label>
  );
}
