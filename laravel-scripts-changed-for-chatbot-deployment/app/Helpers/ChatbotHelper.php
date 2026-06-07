<?php

namespace App\Helpers;

class ChatbotHelper
{
    public static function generateToken($memberId)
    {
        $secret = env('JWT_SECRET', 'SECREAL@4562@SEC');
        
        $header = json_encode(['typ' => 'JWT', 'alg' => 'HS256']);
        $payload = json_encode([
            'member_id' => (int)$memberId,
            'guest_session_id' => null,
            'iat' => time(),
            'exp' => time() + (24 * 60 * 60) // 1 day validity
        ]);
        
        $base64UrlHeader = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($header));
        $base64UrlPayload = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($payload));
        
        $signature = hash_hmac('sha256', $base64UrlHeader . "." . $base64UrlPayload, $secret, true);
        $base64UrlSignature = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($signature));
        
        return $base64UrlHeader . "." . $base64UrlPayload . "." . $base64UrlSignature;
    }
}
