package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestSourceDirReturnsAbsolutePath 验证 sourceDir() 在测试运行时返回的就是
// fake_node.go 所在的绝对目录 (即本测试文件目录)。
func TestSourceDirReturnsAbsolutePath(t *testing.T) {
	got := sourceDir()
	if got == "" {
		t.Fatal("sourceDir() returned empty string; runtime.Caller failed unexpectedly")
	}
	if !filepath.IsAbs(got) {
		t.Errorf("sourceDir() = %q; want absolute path", got)
	}
	// fake_node.go 与本测试文件同目录,所以目录中应该包含 fake_node.go
	if _, err := os.Stat(filepath.Join(got, "fake_node.go")); err != nil {
		t.Errorf("sourceDir()=%q does not contain fake_node.go: %v", got, err)
	}
}

// TestExecutableDirReturnsAbsolutePath 验证 executableDir() 行为。
// `go test` 把 test binary 编译到临时目录,executableDir 应返回该目录。
func TestExecutableDirReturnsAbsolutePath(t *testing.T) {
	got := executableDir()
	if got == "" {
		t.Fatal("executableDir() returned empty; os.Executable failed")
	}
	if !filepath.IsAbs(got) {
		t.Errorf("executableDir() = %q; want absolute path", got)
	}
}

// TestDefaultChainsDirResolvesToRepoChains 验证默认 chains 路径解析到仓库内
// config/chains/ (含 solana.json),无论 cwd 是什么。
func TestDefaultChainsDirResolvesToRepoChains(t *testing.T) {
	// 临时切换到一个无关 cwd,确保解析不依赖 cwd
	tmp := t.TempDir()
	origCwd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(origCwd)
	if err := os.Chdir(tmp); err != nil {
		t.Fatal(err)
	}

	got := defaultChainsDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultChainsDir()=%q; want absolute path resolved from binary/source location", got)
	}
	solanaJSON := filepath.Join(got, "solana.json")
	if _, err := os.Stat(solanaJSON); err != nil {
		t.Errorf("defaultChainsDir()=%q missing expected solana.json: %v", got, err)
	}
	if !strings.HasSuffix(filepath.ToSlash(got), "config/chains") {
		t.Errorf("defaultChainsDir()=%q; expected suffix config/chains", got)
	}
}

// TestDefaultConfigsDirResolvesToFakeNodeConfigs 验证默认 configs 路径。
func TestDefaultConfigsDirResolvesToFakeNodeConfigs(t *testing.T) {
	tmp := t.TempDir()
	origCwd, _ := os.Getwd()
	defer os.Chdir(origCwd)
	os.Chdir(tmp)

	got := defaultConfigsDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultConfigsDir()=%q; want absolute path", got)
	}
	if _, err := os.Stat(filepath.Join(got, "jsonrpc.yaml")); err != nil {
		t.Errorf("defaultConfigsDir()=%q missing jsonrpc.yaml: %v", got, err)
	}
}

// TestDefaultFixturesDirResolvesToFakeNodeFixtures 验证默认 fixtures 路径。
func TestDefaultFixturesDirResolvesToFakeNodeFixtures(t *testing.T) {
	tmp := t.TempDir()
	origCwd, _ := os.Getwd()
	defer os.Chdir(origCwd)
	os.Chdir(tmp)

	got := defaultFixturesDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultFixturesDir()=%q; want absolute path", got)
	}
	if _, err := os.Stat(filepath.Join(got, "solana")); err != nil {
		t.Errorf("defaultFixturesDir()=%q missing solana/ subdir: %v", got, err)
	}
}

// TestResolveDefaultPathFallback 验证当 sourceDir 和 executableDir 路径都不存在
// 资源时,resolveDefaultPath 返回 fallback 字符串。
func TestResolveDefaultPathFallback(t *testing.T) {
	// 用一个肯定不存在的子目录名,sourceDir + relFromSource 不存在,
	// executableDir + relFromExe 也不存在,应返回 fallback。
	const bogus = "__definitely_not_a_real_dir_xyzzy__"
	const fallback = "FALLBACK_RELATIVE_PATH"
	got := resolveDefaultPath(bogus, bogus, fallback)
	if got != fallback {
		t.Errorf("resolveDefaultPath(bogus, bogus, %q) = %q; want fallback", fallback, got)
	}
}

// TestResolveDefaultPathPrefersExecutableDirWhenSourceMissing 验证
// 当 sourceDir 的相对路径不存在但 executableDir 的相对路径存在时,
// resolveDefaultPath 落到第二级 (executable-relative)。
func TestResolveDefaultPathPrefersExecutableDirWhenSourceMissing(t *testing.T) {
	exeDir := executableDir()
	if exeDir == "" {
		t.Skip("executableDir unavailable")
	}
	// 在 test binary 目录下创建一个真实的子目录
	marker := filepath.Join(exeDir, "fake_node_test_marker")
	if err := os.MkdirAll(marker, 0o755); err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(marker)

	got := resolveDefaultPath(
		"__no_such_source_rel__",
		"fake_node_test_marker",
		"FALLBACK",
	)
	if got != marker {
		t.Errorf("resolveDefaultPath returned %q; want exe-relative %q", got, marker)
	}
}
