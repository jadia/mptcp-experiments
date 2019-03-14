#!/usr/bin/python

## Imports

import os
import sys
from subprocess import Popen, PIPE
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from time import sleep
import termcolor as T
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.log import lg
from mininet.topo import SingleSwitchTopo
from mininet.cli import CLI

## Creating topology

class SingleSwitchTopo(Topo):
    "Single switch connected to n hosts."

    def build(self, n=2):
        switch = self.addSwitch('s1')
        # Python's range(N) generates 0..N-1
        for h in range(5):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch, bw=1000)
            self.addLink(host, switch, bw=1000)
        # two more links from h1 (server) to switch
            if h == 0:
                self.addLink(host, switch, bw=1000)
                self.addLink(host, switch, bw=1000)


## Progress bar for iperf

def progress(t):
    while t > 0:
        print T.colored('  %3d seconds left  \r' % (t), 'cyan'),
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print '\r\n'

# Configure routing tables
def routeConfig(h):
    for i in range(1,6):
        lg.info("configuring source-specific routing tables for MPTCP\n")
        # This creates two different routing tables, that we use based on the
        # source-address.
    
    # eth0 config
        j = i-1
        dev = 'h%i-eth0' % i
        h[j].cmdPrint('ip rule add from 10.0.0.%i table 1' % i)
        h[j].cmdPrint('ip route add 10.0.0.0/8 dev %s scope link table 1' % dev)
        h[j].cmdPrint('ip route add default via 10.0.0.1 dev %s table 1' % dev)
    
    # eth1 config
        dev = 'h%i-eth1' % i
        h[j].cmdPrint('ip rule add from 172.168.0.%i table 2' % i)
        h[j].cmdPrint('ip route add 172.168.0.0/18 dev %s scope link table 2' % dev)
        h[j].cmdPrint('ip route add default via 172.168.0.1 dev %s table 2' % dev)

    # extra links route config

    h[0].cmdPrint('ip rule add from 172.168.64.1 table 3')
    h[0].cmdPrint('ip route add 172.168.64.0/18 dev h1-eth2 scope link table 3')
    h[0].cmdPrint('ip route add default via 172.168.64.1 dev h1-eth2 table 3')

    h[0].cmdPrint('ip rule add from 172.168.128.1 table 4')
    h[0].cmdPrint('ip route add 172.168.128.0/18 dev h1-eth3 scope link table 4')
    h[0].cmdPrint('ip route add default via 172.168.128.1 dev h1-eth3 table 4')

## Toggle mptcp
def sysctl_set(key, value):
    """Issue systcl for given param to given value and check for error."""
    p = Popen("sysctl -w %s=%s" % (key, value), shell=True, stdout=PIPE,
              stderr=PIPE)
    # Output should be empty; otherwise, we have an issue.  
    stdout, stderr = p.communicate()
    stdout_expected = "%s = %s\n" % (key, value)
    if stdout != stdout_expected:
        raise Exception("Popen returned unexpected stdout: %s != %s" %
                        (stdout, stdout_expected))
    if stderr:
        raise Exception("Popen returned unexpected stderr: %s" % stderr)


def set_mptcp_enabled(enabled):
    """Enable MPTCP if true, disable if false"""
    e = 1 if enabled else 0
    lg.info("setting MPTCP enabled to %s\n" % e)
    sysctl_set('net.mptcp.mptcp_enabled', e)


## Launch iperf

def iperfLaunch(h):
    lg.info("iperfing")
    sleep(1) # let the server start
    #dst.sendCmd('ping %s -c 2' % (src.IP()))
    seconds=320
    for i in range(1,4):
        cmd = 'iperf -c %s -p 500%i -n 4096M -i 1 &' % (h[0].IP(), i)
        h[i].cmd(cmd)
    # #progress(seconds + 1)
    # src_out = src.waitOutput()
    # lg.info("client output:\n%s\n" % src_out)
    # sleep(0.1)  # hack to wait for iperf server output.
    # out = dst.read(10000)
    # lg.info("server output: %s\n" % out)
    return None


## LaunchPad for various tasks
def simpleTest():
    "Configure interfaces"
    topo = SingleSwitchTopo(n=4)
    net = Mininet(topo, link=TCLink)
    net.start()
    # configure ip's of hosts
    #h1, h2, h3, h4, h5 = net.get( 'h1', 'h2', 'h3', 'h4', 'h5') OBSOLETE
    h1, h2, h3, h4, h5 = net.hosts
    #hosts = ['h%i' % i for i in range(1,6)]
    h1.cmd('ifconfig h1-eth1 172.168.0.1 netmask 255.255.192.0')
    h2.cmd('ifconfig h2-eth1 172.168.0.2 netmask 255.255.192.0')
    h3.cmd('ifconfig h3-eth1 172.168.0.3 netmask 255.255.192.0')
    h4.cmd('ifconfig h4-eth1 172.168.0.4 netmask 255.255.192.0')
    h5.cmd('ifconfig h5-eth1 172.168.0.5 netmask 255.255.192.0')

# configure additional hosts on h1
    h1.cmd('ifconfig h1-eth2 172.168.64.1 netmask 255.255.192.0')
    h1.cmd('ifconfig h1-eth3 172.168.128.1 netmask 255.255.192.0')

    print("Dumping host connections")
    dumpNodeConnections(net.hosts)
    print ("Testing network connectivity")
    net.pingAll()
    #print("using iPerf now! WITHOUT mptcp")
    #iperfLaunch(h2, h1)
    print("using iPerf now! WITH mptcp")
    print("Enabling MPTCP")
    set_mptcp_enabled(True)
    routeConfig(net.hosts)
    h1.cmd('iperf -s -p 5001 -i 1 &')
    h1.cmd('iperf -s -p 5002 -i 1 &')
    h1.cmd('iperf -s -p 5003 -i 1 &')
    h1.cmd('iperf -s -p 5004 -i 1 &')
    h1.cmd('iperf -s -p 5000 -i 1 &')
    iperfLaunch(net.hosts)
    print "\nh5 iperf -c h1 -p 5004 -n 1024M -i 1"
    CLI(net)
    net.stop()
    os.system("sudo mn -c")


if __name__ == '__main__':
    # Tell mininet to print useful information
    setLogLevel('info')
    simpleTest()
