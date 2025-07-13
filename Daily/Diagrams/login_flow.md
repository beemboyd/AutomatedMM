# Login Flow

## Overview
The login system handles authentication with Zerodha Kite API, manages access tokens, and supports multi-user authentication. It includes automatic token refresh and secure credential management.

## Main Login Flow

```mermaid
flowchart TD
    Start([Login Required]) --> CheckToken[Check Existing Token]
    CheckToken --> TokenExists{Token Exists?}
    
    TokenExists -->|No| ManualLogin[Initiate Manual Login]
    TokenExists -->|Yes| ValidateToken[Validate Token]
    
    ValidateToken --> TokenValid{Token Valid?}
    TokenValid -->|Yes| Success[Login Success]
    TokenValid -->|No| RefreshToken[Attempt Token Refresh]
    
    RefreshToken --> RefreshSuccess{Refresh Success?}
    RefreshSuccess -->|Yes| Success
    RefreshSuccess -->|No| ManualLogin
    
    ManualLogin --> LoadCredentials[Load User Credentials]
    LoadCredentials --> OpenBrowser[Open Login URL]
    OpenBrowser --> UserAuth[User Authenticates]
    
    UserAuth --> EnterCreds[Enter Username/Password]
    EnterCreds --> EnterTOTP[Enter TOTP Code]
    EnterTOTP --> KiteRedirect[Kite Redirects]
    
    KiteRedirect --> CaptureToken[Capture Request Token]
    CaptureToken --> ExchangeToken[Exchange for Access Token]
    
    ExchangeToken --> TokenReceived{Token Received?}
    TokenReceived -->|Yes| SaveToken[Save Access Token]
    TokenReceived -->|No| LoginError[Login Failed]
    
    SaveToken --> UpdateContext[Update User Context]
    UpdateContext --> Success
    
    LoginError --> RetryPrompt{Retry?}
    RetryPrompt -->|Yes| ManualLogin
    RetryPrompt -->|No| Exit[Exit Application]
```

## Token Management Flow

```mermaid
flowchart TD
    TokenMgmt([Token Management]) --> LoadToken[Load Saved Token]
    LoadToken --> CheckExpiry[Check Expiry Time]
    
    CheckExpiry --> ExpirySoon{Expires < 30min?}
    ExpirySoon -->|Yes| ProactiveRefresh[Proactive Refresh]
    ExpirySoon -->|No| UseToken[Use Current Token]
    
    ProactiveRefresh --> RefreshAPI[Call Refresh API]
    RefreshAPI --> RefreshOK{Refresh Success?}
    
    RefreshOK -->|Yes| UpdateToken[Update Token]
    RefreshOK -->|No| MarkInvalid[Mark Token Invalid]
    
    UpdateToken --> SaveNewToken[Save New Token]
    SaveNewToken --> UpdateExpiry[Update Expiry Time]
    UpdateExpiry --> UseToken
    
    MarkInvalid --> RequireLogin[Require Fresh Login]
    
    UseToken --> MakeAPICall[Make API Call]
    MakeAPICall --> CallSuccess{Call Success?}
    
    CallSuccess -->|Yes| Continue[Continue Operations]
    CallSuccess -->|No| CheckAuthError{Auth Error?}
    
    CheckAuthError -->|Yes| RequireLogin
    CheckAuthError -->|No| OtherError[Handle Other Error]
```

## Multi-User Login Flow

```mermaid
flowchart TD
    MultiUser([Multi-User Login]) --> SelectUser[Select User Profile]
    SelectUser --> LoadUserConfig[Load User Config]
    
    LoadUserConfig --> UC1[User Credentials]
    LoadUserConfig --> UC2[API Keys]
    LoadUserConfig --> UC3[Token Storage Path]
    
    UC1 --> CheckUserToken[Check User Token]
    UC2 --> CheckUserToken
    UC3 --> CheckUserToken
    
    CheckUserToken --> UserTokenValid{Token Valid?}
    UserTokenValid -->|Yes| SetUserContext[Set User Context]
    UserTokenValid -->|No| UserLogin[User-Specific Login]
    
    UserLogin --> GetUserCreds[Get User Credentials]
    GetUserCreds --> PerformLogin[Perform Login]
    PerformLogin --> SaveUserToken[Save User Token]
    
    SaveUserToken --> SetUserContext
    SetUserContext --> ActivateUser[Activate User Session]
    ActivateUser --> Ready[User Ready]
    
    Ready --> SwitchUser{Switch User?}
    SwitchUser -->|Yes| SaveContext[Save Current Context]
    SwitchUser -->|No| ContinueUser[Continue with User]
    
    SaveContext --> SelectUser
```

## TOTP Handling Flow

```mermaid
flowchart TD
    TOTPFlow([TOTP Required]) --> GetTOTPMethod[Get TOTP Method]
    GetTOTPMethod --> Method{TOTP Source}
    
    Method -->|Manual| ManualEntry[Manual Entry]
    Method -->|Authenticator| AuthApp[From Auth App]
    Method -->|Automated| AutoTOTP[Automated TOTP]
    
    ManualEntry --> PromptUser[Prompt User Input]
    PromptUser --> UserEnters[User Enters Code]
    
    AuthApp --> GetFromApp[Retrieve from App]
    GetFromApp --> AppCode[Get Current Code]
    
    AutoTOTP --> GetSecret[Get TOTP Secret]
    GetSecret --> GenerateCode[Generate TOTP Code]
    
    UserEnters --> ValidateCode[Validate TOTP]
    AppCode --> ValidateCode
    GenerateCode --> ValidateCode
    
    ValidateCode --> CodeValid{Code Valid?}
    CodeValid -->|Yes| ProceedLogin[Continue Login]
    CodeValid -->|No| TOTPError[TOTP Error]
    
    TOTPError --> RetryCount{Retry < 3?}
    RetryCount -->|Yes| GetTOTPMethod
    RetryCount -->|No| LoginFailed[Login Failed]
    
    ProceedLogin --> CompleteAuth[Complete Authentication]
```

## Session Management

```mermaid
flowchart TD
    Session([Session Management]) --> CreateSession[Create Session]
    CreateSession --> SessionData[Initialize Session Data]
    
    SessionData --> SD1[User ID]
    SessionData --> SD2[Access Token]
    SessionData --> SD3[Login Time]
    SessionData --> SD4[Expiry Time]
    
    SD4 --> MonitorSession[Monitor Session]
    MonitorSession --> CheckActive{Check Activity}
    
    CheckActive --> Activity{Last Activity}
    Activity -->|< 5 min| ActiveSession[Keep Active]
    Activity -->|> 5 min| CheckExpiry{Check Expiry}
    
    CheckExpiry -->|Valid| RefreshActivity[Refresh Activity Time]
    CheckExpiry -->|Expired| ExpireSession[Expire Session]
    
    ActiveSession --> UpdateActivity[Update Last Activity]
    RefreshActivity --> UpdateActivity
    
    ExpireSession --> ClearToken[Clear Access Token]
    ClearToken --> RequireReauth[Require Re-authentication]
    
    UpdateActivity --> ContinueSession[Continue Session]
    ContinueSession --> MonitorSession
```

## Error Handling in Login

```mermaid
flowchart TD
    LoginError([Login Error]) --> ErrorType{Error Type}
    
    ErrorType -->|Network| NetworkError[Network Error]
    ErrorType -->|Credentials| CredError[Invalid Credentials]
    ErrorType -->|TOTP| TOTPError[TOTP Failed]
    ErrorType -->|API| APIError[API Error]
    ErrorType -->|Unknown| UnknownError[Unknown Error]
    
    NetworkError --> NE1[Check Connection]
    NE1 --> NE2[Retry with Backoff]
    NE2 --> NE3[Max 3 Retries]
    
    CredError --> CE1[Prompt Correct Creds]
    CE1 --> CE2[Update Stored Creds]
    CE2 --> CE3[Retry Login]
    
    TOTPError --> TE1[Sync Time]
    TE1 --> TE2[Regenerate TOTP]
    TE2 --> TE3[Manual Entry Option]
    
    APIError --> AE1[Check API Status]
    AE1 --> AE2[Use Alternate Endpoint]
    AE2 --> AE3[Contact Support]
    
    UnknownError --> UE1[Log Full Error]
    UE1 --> UE2[Display to User]
    UE2 --> UE3[Manual Intervention]
```

## Credential Storage Flow

```mermaid
flowchart TD
    CredStore([Credential Storage]) --> StorageType{Storage Method}
    
    StorageType -->|Encrypted File| FileStorage[File-Based Storage]
    StorageType -->|Keychain| KeychainStorage[OS Keychain]
    StorageType -->|Environment| EnvStorage[Environment Variables]
    
    FileStorage --> FS1[Encrypt Credentials]
    FS1 --> FS2[Save to File]
    FS2 --> FS3[Set Permissions]
    
    KeychainStorage --> KS1[Access Keychain]
    KS1 --> KS2[Store Securely]
    KS2 --> KS3[OS-Level Protection]
    
    EnvStorage --> ES1[Load from .env]
    ES1 --> ES2[Runtime Only]
    ES2 --> ES3[No Persistence]
    
    RetrieveCreds([Retrieve Credentials]) --> GetMethod{Storage Method}
    GetMethod -->|File| DecryptFile[Decrypt File]
    GetMethod -->|Keychain| ReadKeychain[Read from Keychain]
    GetMethod -->|Env| ReadEnv[Read Environment]
    
    DecryptFile --> ValidateCreds[Validate Credentials]
    ReadKeychain --> ValidateCreds
    ReadEnv --> ValidateCreds
    
    ValidateCreds --> CredsValid{Credentials Valid?}
    CredsValid -->|Yes| UseCreds[Use Credentials]
    CredsValid -->|No| RequestNew[Request New Creds]
```

## Login Integration with Trading System

```mermaid
sequenceDiagram
    participant TradingApp
    participant LoginManager
    participant KiteAPI
    participant TokenManager
    participant UserContext
    participant FileSystem
    
    TradingApp->>LoginManager: Request login
    LoginManager->>TokenManager: Check existing token
    TokenManager-->>LoginManager: Token status
    
    alt Token invalid
        LoginManager->>LoginManager: Initiate manual login
        LoginManager->>KiteAPI: Get login URL
        KiteAPI-->>LoginManager: Return URL
        LoginManager->>LoginManager: Open browser
        LoginManager->>KiteAPI: Exchange request token
        KiteAPI-->>LoginManager: Access token
    end
    
    LoginManager->>TokenManager: Save token
    TokenManager->>FileSystem: Persist token
    
    LoginManager->>UserContext: Update context
    UserContext-->>LoginManager: Context updated
    
    LoginManager-->>TradingApp: Login successful
    TradingApp->>TradingApp: Start trading operations
```