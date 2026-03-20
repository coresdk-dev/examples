// CoreSDK — Gin JWT auth middleware in one line.
//
// Install:  go get github.com/coresdk-dev/sdk-go github.com/gin-gonic/gin
// Run:      go run main.go
// Try:      curl -H "Authorization: Bearer <token>" http://localhost:8080/me

package main

import (
	"net/http"

	"github.com/coresdk-dev/sdk-go/middleware/gin"
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()

	// All routes below require a valid JWT
	r.Use(coresdk.AuthMiddleware())

	r.GET("/me", func(c *gin.Context) {
		user := coresdk.UserFromContext(c)
		c.JSON(http.StatusOK, gin.H{
			"user_id": user.Sub,
			"tenant":  user.TenantID,
			"roles":   user.Roles,
		})
	})

	r.GET("/admin", coresdk.RequireRole("admin"), func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "welcome admin"})
	})

	r.Run(":8080")
}
