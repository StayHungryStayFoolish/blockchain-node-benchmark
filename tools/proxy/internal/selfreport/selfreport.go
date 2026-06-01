// Package selfreport 每秒采集 proxy 自身 cpu_pct/mem_mb,写独立 CSV。
// stdlib only,Linux 通过 /proc/self 读;非 Linux 输出 0/0。
package selfreport

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Reporter struct {
	path     string
	interval time.Duration
	stop     chan struct{}
	wg       sync.WaitGroup
}

func New(path string, interval time.Duration) *Reporter {
	if path == "" {
		path = "./proxy_self.csv"
	}
	if interval <= 0 {
		interval = time.Second
	}
	return &Reporter{path: path, interval: interval, stop: make(chan struct{})}
}

func (r *Reporter) Start() error {
	f, err := os.OpenFile(r.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	w := csv.NewWriter(f)
	if st, _ := f.Stat(); st != nil && st.Size() == 0 {
		_ = w.Write([]string{"timestamp_ns", "cpu_pct", "mem_mb"})
		w.Flush()
	}

	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		defer f.Close()
		prevCPU, prevTime := readCPUTicks(), time.Now()
		t := time.NewTicker(r.interval)
		defer t.Stop()
		for {
			select {
			case <-r.stop:
				w.Flush()
				return
			case now := <-t.C:
				curCPU := readCPUTicks()
				dt := now.Sub(prevTime).Seconds()
				cpu := 0.0
				if dt > 0 {
					cpu = float64(curCPU-prevCPU) / 100.0 / dt * 100.0
				}
				prevCPU, prevTime = curCPU, now
				_ = w.Write([]string{
					strconv.FormatInt(now.UnixNano(), 10),
					fmt.Sprintf("%.2f", cpu),
					fmt.Sprintf("%.2f", readMemMB()),
				})
				w.Flush()
			}
		}
	}()
	return nil
}

func (r *Reporter) Stop() {
	close(r.stop)
	r.wg.Wait()
}

// readCPUTicks 读 /proc/self/stat 字段 14+15 (utime+stime, clock ticks)。
func readCPUTicks() int64 {
	b, err := os.ReadFile("/proc/self/stat")
	if err != nil {
		return 0
	}
	s := string(b)
	rp := strings.LastIndex(s, ")")
	if rp < 0 || rp+2 >= len(s) {
		return 0
	}
	fields := strings.Fields(s[rp+2:])
	if len(fields) < 13 {
		return 0
	}
	ut, _ := strconv.ParseInt(fields[11], 10, 64)
	st, _ := strconv.ParseInt(fields[12], 10, 64)
	return ut + st
}

// readMemMB 读 /proc/self/status VmRSS (kB) → MB。
func readMemMB() float64 {
	b, err := os.ReadFile("/proc/self/status")
	if err != nil {
		return 0
	}
	for _, line := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(line, "VmRSS:") {
			fields := strings.Fields(line)
			if len(fields) < 2 {
				return 0
			}
			kb, _ := strconv.ParseFloat(fields[1], 64)
			return kb / 1024.0
		}
	}
	return 0
}
