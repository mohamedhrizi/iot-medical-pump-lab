# Network Configuration Checklist for Wazuh Integration

## Required Network Ports

### Wazuh Agent → Manager Communication

- **1514/UDP** - Agent status/keepalive (can be unreliable over internet)
- **1515/TCP** - Agent data transmission (reliable command/alert channel)
- **514/UDP** - Syslog (optional, for centralized logging)

### Firewall Rules

```bash
# On Wazuh Manager host - allow inbound from agents
sudo ufw allow from 0.0.0.0/0 to any port 1514 proto udp
sudo ufw allow from 0.0.0.0/0 to any port 1515 proto tcp

# Restrict to known agent IPs if possible
sudo ufw allow from <AGENT_IP> to any port 1514 proto udp
sudo ufw allow from <AGENT_IP> to any port 1515 proto tcp

# Verify rules
sudo ufw status
```

### Verify Network Connectivity

```bash
# From lab host (Wazuh Agent) to Wazuh Manager
netcat -zv <WAZUH_MANAGER_IP> 1514  # UDP test
netcat -zv <WAZUH_MANAGER_IP> 1515  # TCP test

# Or use nc with timeout
echo "test" | nc -w 1 <WAZUH_MANAGER_IP> 1515
```

## Time Synchronization

### Critical: NTP/Chrony Configuration

Audit log timestamps and Wazuh alerts must be synchronized for proper alert correlation.

```bash
# Check current time sync status
timedatectl status

# Expected output:
# System clock synchronized: yes
# NTP service: active

# If not synchronized, enable NTP
sudo timedatectl set-ntp true

# Or configure Chrony manually
sudo apt-get install chrony
sudo systemctl start chrony
sudo systemctl status chrony

# Verify sync with server
chronyc tracking

# Expected:
# Reference ID    : C0248F97 (ntp.ubuntu.com)
# Stratum         : 2
# Ref time (UTC)  : Mon Jul 14 17:40:00 2026
# System time     : 0.000001234 seconds ahead of NTP time
```

### Configure Chrony on Lab Host

```bash
# Edit /etc/chrony/chrony.conf
sudo nano /etc/chrony/chrony.conf

# Add your NTP server (or use Ubuntu defaults)
server ntp.ubuntu.com iburst
server 0.ubuntu.pool.ntp.org iburst
server 1.ubuntu.pool.ntp.org iburst

# Restart service
sudo systemctl restart chrony

# Verify sync
chronyc sources -v
```

### Wazuh Manager Time Check

```bash
# On Wazuh Manager
date
timedatectl status

# Compare with lab host
ssh user@<LAB_HOST> date

# Acceptable skew: < 5 seconds (typically)
```

## File Permissions

### Audit Log Accessibility

The Wazuh Agent must be able to read `audit.log` from the pump simulator.

```bash
# Lab host: Directory permissions
ls -ld ~
# Expected: drwx------  (700) for home directory is typical, but needs read for wazuh

# Grant read+execute on home directory
chmod o+rx ~

# Check audit.log file
ls -l ~/iomt-lab/audit.log
# Expected: -rw-r--r-- (644) or at least readable

# Grant read permission if needed
chmod o+r ~/iomt-lab/audit.log

# Full setup
chmod o+rx ~
chmod o+r ~/iomt-lab/audit.log

# Verify
ls -ld ~
ls -l ~/iomt-lab/audit.log
```

### Wazuh Agent Permissions

```bash
# Check Wazuh agent user
grep wazuh /etc/passwd
# Expected: wazuh:x:1001:1001:...

# Verify agent can read pump logs
sudo -u wazuh cat ~/iomt-lab/audit.log | head -5

# If permission denied, adjust:
sudo setfacl -m u:wazuh:rx ~
sudo setfacl -m u:wazuh:r ~/iomt-lab/audit.log

# Verify ACL
getfacl ~
```

## Wazuh Agent Registration

### Step 1: On Wazuh Manager

```bash
# Import agent key (if not auto-enrolled)
sudo /var/ossec/bin/manage_agents

# Or use agent enrollment:
sudo /var/ossec/bin/agent-auth -m <MANAGER_IP> -A <AGENT_NAME>
```

### Step 2: Configure Agent

Edit `/var/ossec/etc/ossec.conf` on lab host:

```xml
<ossec_config>
  <client>
    <server>
      <address><WAZUH_MANAGER_IP></address>
      <port>1514</port>
      <protocol>udp</protocol>
    </server>
    <notify_time>10</notify_time>
    <time-reconnect>60</time-reconnect>
    <auto_restart>yes</auto_restart>
  </client>

  <!-- Monitor audit.log -->
  <localfile>
    <log_format>json</log_format>
    <path>~/iomt-lab/audit.log</path>
  </localfile>

  <!-- Optional: Monitor pump simulator stderr -->
  <localfile>
    <log_format>syslog</log_format>
    <path>~/iomt-lab/pump_sim.log</path>
  </localfile>
</ossec_config>
```

### Step 3: Restart Agent

```bash
sudo systemctl restart wazuh-agent
sudo systemctl status wazuh-agent

# Check agent logs
sudo tail -f /var/ossec/logs/ossec.log | grep agent
```

## Connectivity Verification

### From Lab Host

```bash
# Test UDP connectivity to manager
echo "test" | nc -u <WAZUH_MANAGER_IP> 1514

# Test TCP connectivity to manager
echo "test" | nc <WAZUH_MANAGER_IP> 1515

# Check agent status
sudo /var/ossec/bin/wazuh-control status

# Expected: wazuh-authd is running
#           wazuh-execd is running
#           wazuh-agentd is running
```

### From Wazuh Manager

```bash
# List connected agents
sudo /var/ossec/bin/agent-control -l

# Expected output:
ID: 000, Name: manager, IP: 127.0.0.1, Status: Active
ID: 001, Name: <AGENT_NAME>, IP: <AGENT_IP>, Status: Active

# Get agent status details
sudo /var/ossec/bin/agent-control -i 001
```

## Quick Verification Checklist

- [ ] Wazuh Manager is running: `sudo systemctl status wazuh-manager`
- [ ] Wazuh Agent is running: `sudo systemctl status wazuh-agent`
- [ ] Manager listening on 1514: `sudo netstat -tlnup | grep 1514`
- [ ] Agent can reach manager: `nc -zv <MANAGER_IP> 1514`
- [ ] Time synced on both hosts: `timedatectl status`
- [ ] audit.log readable by wazuh: `sudo -u wazuh cat ~/iomt-lab/audit.log`
- [ ] Rules deployed: `sudo ls -la /var/ossec/etc/rules/local_rules.xml`
- [ ] Manager restarted after rule deployment: `sudo systemctl restart wazuh-manager`
- [ ] Agent connected to manager: `sudo /var/ossec/bin/agent-control -l | grep Active`
- [ ] Events flowing: `sudo tail -f /var/ossec/logs/alerts/alerts.json`

## Troubleshooting Common Issues

### Agent not connecting to Manager

```bash
# Check agent logs
sudo tail -100 /var/ossec/logs/ossec.log | grep -i error

# Common issues:
# - "Cannot connect to agent": Network blocked or manager IP wrong
# - "Authentication failed": Agent not properly registered
# - "Connection timeout": Manager not listening or firewall blocked
```

### Audit events not being ingested

```bash
# Check if audit.log exists and has content
ls -l ~/iomt-lab/audit.log
wc -l ~/iomt-lab/audit.log

# Check agent file monitoring
sudo grep "audit.log" /var/ossec/logs/ossec.log

# Verify file format is JSON
jq . ~/iomt-lab/audit.log | head -3
```

### Rules not triggering

```bash
# Verify rules are loaded
sudo grep "100111\|100112\|100113" /var/ossec/logs/ossec.log

# Check rule syntax
sudo /var/ossec/bin/wazuh-control info

# Test rules manually
sudo /var/ossec/bin/wazuh-logtest < sample_events.json
```

## Performance Tuning (Optional)

### Increase Agent Alert Buffer

Edit `/var/ossec/etc/ossec.conf` on agent:

```xml
<client>
  <notify_time>10</notify_time>
  <time-reconnect>60</time-reconnect>
  <queue_size>16384</queue_size>
</client>
```

### Increase Manager Alert Processing

Edit `/var/ossec/etc/ossec.conf` on manager:

```xml
<alerting>
  <log_alert_level>3</log_alert_level>
  <email_notification>yes</email_notification>
</alerting>
```

## References

- Wazuh Network Architecture: https://documentation.wazuh.com/current/deployment-options/index.html
- Agent Installation: https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html
- NTP Configuration: https://ubuntu.com/server/docs/service-ntp
