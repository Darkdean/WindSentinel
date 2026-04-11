rule MacSuspiciousHash
{
    meta:
        description = "known macos malicious hashes"
    strings:
        $hash1 = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    condition:
        $hash1
}

rule SuspiciousURL
{
    meta:
        description = "known malicious urls"
    strings:
        $url1 = "http://malicious.example.com"
        $url2 = "https://evil.example.com"
    condition:
        any of them
}
