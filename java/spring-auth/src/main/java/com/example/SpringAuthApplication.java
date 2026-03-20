package com.example;

import io.coresdk.AuthDecision;
import io.coresdk.CoreSDK;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@SpringBootApplication
@RestController
public class SpringAuthApplication {

    @Autowired
    private CoreSDK sdk;

    public static void main(String[] args) {
        SpringApplication.run(SpringAuthApplication.class, args);
    }

    @GetMapping("/me")
    public ResponseEntity<Map<String, Object>> me(
            @RequestHeader(value = "Authorization", defaultValue = "") String authHeader) {

        String token = authHeader.startsWith("Bearer ")
                ? authHeader.substring(7)
                : authHeader;

        AuthDecision decision = sdk.authorize(token, "/me", "GET").join();

        if (!decision.isAllowed()) {
            return ResponseEntity.status(403)
                    .body(Map.of("error", "forbidden", "reason", String.valueOf(decision.getReason())));
        }

        return ResponseEntity.ok(Map.of(
                "sub", decision.getClaims().getSub(),
                "tenant", decision.getClaims().getTenantId(),
                "roles", decision.getClaims().getRoles()
        ));
    }
}
