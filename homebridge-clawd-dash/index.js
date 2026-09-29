'use strict';

// Publishes Clawd Dash as a HomeKit Television. Power maps to the Pi's HDMI
// output, and each "input" is a dashboard view. All state lives in
// server.py's /control endpoint; this just translates HomeKit <-> HTTP.
//
// The input list comes from server.py's MODES too, re-synced on every poll,
// so adding/removing/renaming a screensaver there shows up in the Home app
// without touching or restarting this plugin.

const fs = require('fs');
const path = require('path');

const PLUGIN_NAME = 'homebridge-clawd-dash';
const PLATFORM_NAME = 'ClawdDash';

module.exports = (api) => {
  api.registerPlatform(PLATFORM_NAME, ClawdDashPlatform);
};

class ClawdDashPlatform {
  constructor(log, config, api) {
    this.log = log;
    this.api = api;
    this.name = config.name || 'Clawd Dash';
    this.baseUrl = (config.url || 'http://localhost:8080').replace(/\/+$/, '');
    this.pollMs = (config.pollInterval || 5) * 1000;
    this.state = { power: true, mode: 'auto' };
    this.inputs = new Map(); // mode id -> InputSource service

    // HomeKit input Identifiers must stay stable per mode across restarts
    // and list edits, so they're assigned once and persisted, never reused.
    // The last-seen mode list is cached too, so inputs exist at startup even
    // if server.py isn't up yet.
    this.storePath = path.join(api.user.storagePath(), 'clawd-dash-inputs.json');
    this.store = this.loadStore();

    api.on('didFinishLaunching', () => this.publish());
  }

  loadStore() {
    try {
      const s = JSON.parse(fs.readFileSync(this.storePath, 'utf8'));
      return { identifiers: s.identifiers || {}, modes: s.modes || [] };
    } catch {
      return { identifiers: {}, modes: [] };
    }
  }

  saveStore() {
    try {
      fs.writeFileSync(this.storePath, JSON.stringify(this.store, null, 2));
    } catch (err) {
      this.log.warn(`Couldn't save input list: ${err.message}`);
    }
  }

  identifierFor(id) {
    const ids = this.store.identifiers;
    if (!ids[id]) ids[id] = Math.max(0, ...Object.values(ids)) + 1;
    return ids[id];
  }

  modeForIdentifier(identifier) {
    return [...this.inputs.keys()].find((id) => this.store.identifiers[id] === identifier);
  }

  async control(params = {}) {
    const qs = new URLSearchParams(params).toString();
    const res = await fetch(`${this.baseUrl}/control${qs ? '?' + qs : ''}`, {
      signal: AbortSignal.timeout(5000),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    return body;
  }

  // Adds/removes/renames InputSource services to match `modes`. HAP bumps the
  // accessory's config number on service changes, so paired iPhones refetch.
  syncInputs(modes) {
    const { Service, Characteristic } = this.api.hap;
    const prevNames = new Map(this.store.modes.map((m) => [m.id, m.name]));
    const wanted = new Set(modes.map((m) => m.id));

    for (const { id, name } of modes) {
      const input = this.inputs.get(id);
      if (!input) {
        const created = this.accessory.addService(Service.InputSource, name, id);
        created
          .setCharacteristic(Characteristic.Identifier, this.identifierFor(id))
          .setCharacteristic(Characteristic.ConfiguredName, name)
          .setCharacteristic(Characteristic.IsConfigured, Characteristic.IsConfigured.CONFIGURED)
          .setCharacteristic(Characteristic.InputSourceType, Characteristic.InputSourceType.APPLICATION)
          .setCharacteristic(Characteristic.CurrentVisibilityState, Characteristic.CurrentVisibilityState.SHOWN);
        this.tv.addLinkedService(created);
        this.inputs.set(id, created);
        if (this.published) this.log.info(`Added input: ${name}`);
      } else if (prevNames.has(id) && prevNames.get(id) !== name) {
        // Only push server-side renames, so a rename done in the Home app sticks.
        input.updateCharacteristic(Characteristic.ConfiguredName, name);
        this.log.info(`Renamed input: ${prevNames.get(id)} -> ${name}`);
      }
    }

    for (const [id, input] of this.inputs) {
      if (wanted.has(id)) continue;
      this.tv.removeLinkedService(input);
      this.accessory.removeService(input);
      this.inputs.delete(id);
      this.log.info(`Removed input: ${prevNames.get(id) || id}`);
    }

    if (JSON.stringify(modes) !== JSON.stringify(this.store.modes)) {
      this.store.modes = modes;
      this.saveStore();
    }
  }

  apply({ power, mode, modes }) {
    const { Characteristic } = this.api.hap;
    if (Array.isArray(modes) && modes.length) this.syncInputs(modes);
    this.state = { power, mode };
    this.tv.updateCharacteristic(Characteristic.Active, power ? 1 : 0);
    const identifier = this.store.identifiers[mode];
    if (identifier && this.inputs.has(mode)) {
      this.tv.updateCharacteristic(Characteristic.ActiveIdentifier, identifier);
    }
  }

  async publish() {
    const { Service, Characteristic, Categories, uuid, HapStatusError, HAPStatus } = this.api.hap;

    // Seed the input list before publishing on a first run with no cache.
    let initial = null;
    try {
      initial = await this.control();
    } catch (err) {
      this.log.warn(`Dashboard server not reachable yet: ${err.message}`);
    }

    // TVs must be external accessories: HomeKit won't show a TV's inputs
    // when it sits behind a bridge, so this gets paired separately.
    this.accessory = new this.api.platformAccessory(
      this.name, uuid.generate(`${PLUGIN_NAME}:${this.name}`), Categories.TELEVISION);

    this.accessory.getService(Service.AccessoryInformation)
      .setCharacteristic(Characteristic.Manufacturer, 'Clawd Dash')
      .setCharacteristic(Characteristic.Model, 'Raspberry Pi Dashboard')
      .setCharacteristic(Characteristic.SerialNumber, 'clawd-dash');

    const tv = this.tv = this.accessory.addService(Service.Television, this.name);
    tv.setCharacteristic(Characteristic.ConfiguredName, this.name);
    tv.setCharacteristic(Characteristic.SleepDiscoveryMode,
      Characteristic.SleepDiscoveryMode.ALWAYS_DISCOVERABLE);

    const commFailure = (err, what) => {
      this.log.error(`Failed to ${what}: ${err.message}`);
      return new HapStatusError(HAPStatus.SERVICE_COMMUNICATION_FAILURE);
    };

    // Getters return the cached state so the Home app never waits on HTTP;
    // the poll below keeps it current.
    tv.getCharacteristic(Characteristic.Active)
      .onGet(() => (this.state.power ? 1 : 0))
      .onSet(async (value) => {
        try {
          this.apply(await this.control({ power: value ? 'on' : 'off' }));
        } catch (err) {
          throw commFailure(err, 'set power');
        }
      });

    tv.getCharacteristic(Characteristic.ActiveIdentifier)
      .onGet(() => this.store.identifiers[this.state.mode] || 1)
      .onSet(async (value) => {
        const mode = this.modeForIdentifier(value);
        if (!mode) return;
        try {
          this.apply(await this.control({ mode }));
        } catch (err) {
          throw commFailure(err, `switch to ${mode}`);
        }
      });

    // Required for the TV tile to render; there's no remote to drive.
    tv.getCharacteristic(Characteristic.RemoteKey).onSet(() => {});

    if (this.store.modes.length) this.syncInputs(this.store.modes);
    if (initial) this.apply(initial);

    this.api.publishExternalAccessories(PLUGIN_NAME, [this.accessory]);
    this.published = true;

    setInterval(async () => {
      try {
        this.apply(await this.control());
      } catch (err) {
        this.log.debug(`Poll failed: ${err.message}`);
      }
    }, this.pollMs);
  }
}
