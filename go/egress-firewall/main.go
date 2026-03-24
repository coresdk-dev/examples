// Example: SSRF firewall — block outbound requests to internal IPs.
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"

	coresdk "github.com/coresdk-dev/sdk-go"
)

func main() {
	sdk, err := coresdk.FromEnv()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to create SDK: %v\n", err)
		os.Exit(1)
	}
	defer sdk.Close()

	ctx := context.Background()

	fmt.Println("=== SSRF Firewall Example ===\n")

	// Direct egress check
	urls := []string{
		"https://api.example.com/data",
		"http://169.254.169.254/latest/meta-data/",
		"http://192.168.1.1/admin",
	}
	for _, url := range urls {
		decision, err := sdk.CheckEgress(ctx, url)
		if err != nil {
			fmt.Printf("  ERROR  %s: %v\n", url, err)
			continue
		}
		if decision.Allowed {
			fmt.Printf("  ALLOWED  %s\n", url)
		} else {
			fmt.Printf("  BLOCKED  %s  (%s)\n", url, decision.Reason)
		}
	}

	fmt.Println()

	// Use CoreSDKHTTPClient for automatic SSRF checking
	fmt.Println("Using CoreSDKHTTPClient (auto-checks before every request):")
	client := coresdk.NewCoreSDKHTTPClient(sdk)

	req, _ := http.NewRequestWithContext(ctx, "GET", "http://10.0.0.1/internal", nil)
	_, err = client.Do(req)
	if err != nil {
		fmt.Printf("  Blocked: %v\n", err)
	}
}
