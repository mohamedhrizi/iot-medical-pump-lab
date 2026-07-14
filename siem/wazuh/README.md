# Wazuh Integration for IoMT Infusion Pump Lab

This directory contains Wazuh rules and configuration for monitoring cybersecurity events in the IoMT pump simulator.

## Architecture

```
Pump Simulator (audit.log)
        ↓ (JSON events)
Wazuh Agent (file monitor)
        ↓ (1514/UDP, 1515/TCP)
Wazuh Manager (SIEM)
        ↓
Wazuh Alerts (alerts.json)
```

## Files

- **local_rules.xml** - Custom Wazuh rules for pump commands and rejections
- **network_checklist.md** - Network and system prerequisites
- **README.md** - This file

## Rule Hierarchy

All IoMT pump events are organized in a hierarchical rule structure:

```
100100 (Parent: All IoMT audit events)
├── 100110 (pump.command events)
│   ├── 100111 (SET_RATE - Level 10, T0836/T0831)
│   ├── 100112 (DISABLE_ALARM - Level 13, T0878)
│   ├── 100113 (STOP - Level 12, T0813)
│   ├── 100114 (PAUSE - Level 3)
│   ├── 100115 (RESUME - Level 3)
│   └── 100116 (ENABLE_ALARM - Level 3)
├── 100120 (pump.command_rejected - Level 8, T0855)
├── 100121 (Multiple rejections - Level 11, pattern detection)
└── 100130 (Non-localhost source - Level 9, T0834)
```

## Deployment Steps

### Step 1: Copy Rules to Wazuh Manager

On the Wazuh Manager host:

```bash
# Copy the rules file
sudo cp local_rules.xml /var/ossec/etc/rules/

# Verify ownership and permissions
sudo chown root:wazuh /var/ossec/etc/rules/local_rules.xml
sudo chmod 640 /var/ossec/etc/rules/local_rules.xml
```

### Step 2: Configure Wazuh Agent on Lab Host

Edit `/var/ossec/etc/ossec.conf` on the Wazuh Agent:

```xml
<!-- Monitor audit.log -->
<localfile>
    <log_format>json</log_format>
    <path>~/iomt-lab/audit.log</path>
    <label key="component">pump</label>
</localfile>
```

### Step 3: Restart Wazuh Manager

```bash
# Test rule syntax
sudo /var/ossec/bin/wazuh-control info

# Restart the manager
sudo systemctl restart wazuh-manager

# Verify status
sudo systemctl status wazuh-manager
```

### Step 4: Restart Wazuh Agent

```bash
# On the lab host
sudo systemctl restart wazuh-agent

# Verify connection
sudo /var/ossec/bin/agent-control -i
```

## Testing the Rules

### Option 1: Using wazuh-logtest (Recommended)

On the Wazuh Manager, test rules against sample events:

```bash
# Start the rule testing utility
sudo /var/ossec/bin/wazuh-logtest

# Paste JSON audit events, one per line:
# Example SET_RATE event:
{"timestamp": "2026-07-14T17:40:00+00:00", "event": "pump.command", "component": "pump", "src_ip": "127.0.0.1", "device_id": "PUMP-IOMT-01", "patient_id": "PT-50001", "command": "SET_RATE", "old_rate": 50.0, "new_rate": 120.0}

# Example DISABLE_ALARM event:
{"timestamp": "2026-07-14T17:40:05+00:00", "event": "pump.command", "component": "pump", "src_ip": "192.168.1.100", "device_id": "PUMP-IOMT-01", "patient_id": "PT-50001", "command": "DISABLE_ALARM", "severity": "critical"}

# Example command rejection:
{"timestamp": "2026-07-14T17:40:10+00:00", "event": "pump.command_rejected", "component": "pump", "src_ip": "127.0.0.1", "command": "SET_RATE", "reason": "valeur_invalide", "raw": "not_a_number"}
```

### Option 2: Generate Real Events

Run the baseline traffic generator to produce legitimate audit events:

```bash
# From the project root
python3 tools/baseline_traffic_gen.py --duration 60 --interval 5

# Monitor alerts in real-time (on Wazuh Manager)
tail -f /var/ossec/logs/alerts/alerts.json | jq '.data.srcip, .data.audit.command'
```

### Option 3: Send Attack Simulation

Use the command client to trigger high-severity rules:

```bash
# In separate terminals:

# Terminal 1: Start pump simulator
python3 pump/pump.py

# Terminal 2: Send commands to trigger rules
python3 pump/command_client.py DISABLE_ALARM
python3 pump/command_client.py SET_RATE 500
python3 pump/command_client.py STOP

# Terminal 3: Monitor Wazuh alerts
sudo tail -f /var/ossec/logs/alerts/alerts.json
```

## Verifying Rules Trigger

### Check Alert Counts by Rule ID

```bash
# Count alerts by rule
sudo jq '.rule.id' /var/ossec/logs/alerts/alerts.json | sort | uniq -c

# Filter by specific rule (e.g., 100112 - DISABLE_ALARM)
sudo jq 'select(.rule.id == 100112)' /var/ossec/logs/alerts/alerts.json

# View command alerts with details
sudo jq 'select(.rule.groups[] | contains("iomt_pump_security")) | {rule_id: .rule.id, command: .data.command, src_ip: .data.src_ip}' /var/ossec/logs/alerts/alerts.json
```

### Monitor Live Alerts

```bash
# Real-time tail with JSON formatting
sudo tail -f /var/ossec/logs/alerts/alerts.json | jq 'select(.rule.level >= 10)'

# Watch for DISABLE_ALARM specifically
sudo tail -f /var/ossec/logs/alerts/alerts.json | jq 'select(.data.command == "DISABLE_ALARM")'
```

## Audit Log Schema

The pump simulator writes audit events in this JSON format:

```json
{
  "timestamp": "2026-07-14T17:40:00+00:00",
  "event": "pump.command" | "pump.command_rejected",
  "component": "pump",
  "src_ip": "127.0.0.1",
  "device_id": "PUMP-IOMT-01",
  "patient_id": "PT-50001",
  "command": "SET_RATE" | "PAUSE" | "RESUME" | "DISABLE_ALARM" | "ENABLE_ALARM" | "STOP",
  "reason": "valeur_invalide" | "commande_inconnue" (for rejected events),
  "old_rate": 50.0 (for SET_RATE),
  "new_rate": 120.0 (for SET_RATE),
  "severity": "critical" | "high" | "medium" (optional),
  "raw": "raw_input_string" (for rejected events)
}
```

## Troubleshooting

### Rules Not Matching

1. **Verify JSON parsing:**
   ```bash
   # Check that audit.log is valid JSON
   jq . ~/iomt-lab/audit.log | head -10
   ```

2. **Check Wazuh agent is reading the file:**
   ```bash
   sudo tail -f /var/ossec/logs/ossec.log | grep audit.log
   ```

3. **Validate rule syntax:**
   ```bash
   sudo /var/ossec/bin/wazuh-control info
   sudo systemctl restart wazuh-manager
   ```

### Permissions Issues

```bash
# Ensure audit.log is readable by Wazuh agent
chmod o+r ~/iomt-lab/audit.log

# Ensure parent directory is accessible
chmod o+rx ~
```

### Network Connectivity

```bash
# Verify agent can reach manager on 1514/UDP and 1515/TCP
netstat -tuln | grep 1514
netstat -tuln | grep 1515

# Test connectivity from agent to manager
nc -zu <wazuh_manager_ip> 1514
```

## Customization

### Adding New Rules

Edit `local_rules.xml` and add rules following the existing pattern:

```xml
<rule id="100140" level="X" parent="100110">
  <field name="command">NEW_COMMAND</field>
  <description>Your description</description>
  <mitre>
    <id>TXXXX</id>
  </mitre>
</rule>
```

### Adjusting Alert Levels

Modify the `level` attribute (0-15, where 0 is noalert):

- **0** - Noalert (parent rules)
- **3** - Informational
- **5** - Notice
- **8-10** - Warning/Security
- **13-15** - Critical (typically triggers email alerts)

## MITRE ATT&CK Mappings

| Rule | Command | MITRE ID | Description |
|------|---------|----------|-------------|
| 100111 | SET_RATE | T0836, T0831 | Modify program state / manipulate I/O |
| 100112 | DISABLE_ALARM | T0878 | Alarm suppression |
| 100113 | STOP | T0813 | Shutdown/restart device |
| 100120 | (rejected) | T0855 | Unauthorized command message |
| 100130 | (any) | T0834 | Unauthorized command message (non-local) |

For more information: https://attack.mitre.org/matrices/ics/

## References

- Wazuh Documentation: https://documentation.wazuh.com/
- Wazuh Rule Writing: https://documentation.wazuh.com/current/user-manual/ruleset/rules.html
- MITRE ATT&CK (ICS): https://attack.mitre.org/matrices/ics/
- Pump Audit Schema: `security/audit.py`
