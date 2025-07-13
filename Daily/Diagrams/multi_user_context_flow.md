# Multi-User Context Flow

## Overview
The multi-user context system allows multiple traders to use the same trading system simultaneously, each with their own credentials, portfolios, and trading parameters. The UserContextManager handles user switching, isolation, and concurrent operations.

## User Context Management Flow

```mermaid
flowchart TD
    Start([System Start]) --> LoadUserConfig[Load User Configuration]
    LoadUserConfig --> ParseUsers[Parse User Profiles]
    
    ParseUsers --> UserList[Create User List]
    UserList --> DefaultUser{Default User Set?}
    
    DefaultUser -->|Yes| LoadDefault[Load Default User]
    DefaultUser -->|No| SelectUser[User Selection Menu]
    
    LoadDefault --> InitContext[Initialize User Context]
    SelectUser --> InitContext
    
    InitContext --> LoadUserData[Load User-Specific Data]
    LoadUserData --> UD1[Credentials]
    LoadUserData --> UD2[Trading Parameters]
    LoadUserData --> UD3[Portfolio State]
    LoadUserData --> UD4[Order History]
    
    UD1 --> CreateContext[Create Context Object]
    UD2 --> CreateContext
    UD3 --> CreateContext
    UD4 --> CreateContext
    
    CreateContext --> ActivateContext[Activate User Context]
    ActivateContext --> SetGlobal[Set as Current User]
    SetGlobal --> Ready[System Ready for User]
```

## User Switching Flow

```mermaid
flowchart TD
    SwitchRequest([Switch User Request]) --> SaveCurrent[Save Current Context]
    SaveCurrent --> SC1[Save Open Positions]
    SaveCurrent --> SC2[Save Pending Orders]
    SaveCurrent --> SC3[Save User State]
    SaveCurrent --> SC4[Close Connections]
    
    SC4 --> SelectNewUser[Select New User]
    SelectNewUser --> ValidateUser{User Valid?}
    
    ValidateUser -->|No| ErrorMsg[Show Error]
    ValidateUser -->|Yes| LoadNewUser[Load New User Context]
    
    ErrorMsg --> KeepCurrent[Keep Current User]
    
    LoadNewUser --> LU1[Load Credentials]
    LoadNewUser --> LU2[Load Portfolio]
    LoadNewUser --> LU3[Load Settings]
    LoadNewUser --> LU4[Initialize APIs]
    
    LU4 --> ActivateNew[Activate New Context]
    ActivateNew --> UpdateGlobal[Update Global Context]
    UpdateGlobal --> NotifySwitch[Notify All Components]
    
    NotifySwitch --> RestartServices[Restart User Services]
    RestartServices --> SwitchComplete[Switch Complete]
```

## Multi-User Isolation

```mermaid
flowchart TD
    UserContext([User Context]) --> IsolationLayers[Isolation Layers]
    
    IsolationLayers --> DataIsolation[Data Isolation]
    IsolationLayers --> APIIsolation[API Isolation]
    IsolationLayers --> FileIsolation[File Isolation]
    IsolationLayers --> StateIsolation[State Isolation]
    
    DataIsolation --> DI1[Separate Databases]
    DataIsolation --> DI2[User-Specific Tables]
    DataIsolation --> DI3[Isolated Cache]
    
    APIIsolation --> AI1[Individual API Keys]
    APIIsolation --> AI2[Separate Connections]
    APIIsolation --> AI3[User Token Management]
    
    FileIsolation --> FI1[User Directories]
    FileIsolation --> FI2[Separate Log Files]
    FileIsolation --> FI3[Individual Config Files]
    
    StateIsolation --> SI1[User State Files]
    StateIsolation --> SI2[Separate Trading State]
    StateIsolation --> SI3[Individual Session Data]
```

## Concurrent User Operations

```mermaid
flowchart TD
    MultiUserOps([Concurrent Operations]) --> UserScheduler[User Operation Scheduler]
    
    UserScheduler --> User1[User 1 Operations]
    UserScheduler --> User2[User 2 Operations]
    UserScheduler --> UserN[User N Operations]
    
    User1 --> U1Scan[Scanner Running]
    User1 --> U1Orders[Order Placement]
    User1 --> U1Monitor[Position Monitoring]
    
    User2 --> U2Scan[Scanner Running]
    User2 --> U2Orders[Order Placement]
    User2 --> U2Monitor[Position Monitoring]
    
    UserN --> UNScan[Scanner Running]
    UserN --> UNOrders[Order Placement]
    UserN --> UNMonitor[Position Monitoring]
    
    U1Scan --> ResourcePool[Shared Resource Pool]
    U2Scan --> ResourcePool
    UNScan --> ResourcePool
    
    ResourcePool --> RP1[CPU Allocation]
    ResourcePool --> RP2[Memory Management]
    ResourcePool --> RP3[API Rate Limiting]
    ResourcePool --> RP4[Thread Pool]
```

## User Context Object Structure

```mermaid
graph TD
    UserContext[User Context Object] --> BasicInfo[Basic Information]
    UserContext --> Credentials[Credentials]
    UserContext --> TradingParams[Trading Parameters]
    UserContext --> Portfolio[Portfolio Data]
    UserContext --> Sessions[Session Management]
    
    BasicInfo --> BI1[User ID]
    BasicInfo --> BI2[Username]
    BasicInfo --> BI3[Email]
    BasicInfo --> BI4[Active Status]
    
    Credentials --> CR1[API Key]
    Credentials --> CR2[API Secret]
    Credentials --> CR3[Access Token]
    Credentials --> CR4[Token Expiry]
    
    TradingParams --> TP1[Risk Limits]
    TradingParams --> TP2[Position Sizes]
    TradingParams --> TP3[Allowed Strategies]
    TradingParams --> TP4[Trading Hours]
    
    Portfolio --> PF1[Current Positions]
    Portfolio --> PF2[Order History]
    Portfolio --> PF3[P&L Data]
    Portfolio --> PF4[Capital Allocation]
    
    Sessions --> SS1[Login Time]
    Sessions --> SS2[Last Activity]
    Sessions --> SS3[Session ID]
    Sessions --> SS4[Connection Status]
```

## User-Aware Component Flow

```mermaid
flowchart TD
    Component([Trading Component]) --> GetContext[Get Current Context]
    GetContext --> CheckContext{Context Valid?}
    
    CheckContext -->|No| ErrorHandle[Handle Error]
    CheckContext -->|Yes| GetUserID[Extract User ID]
    
    GetUserID --> LoadUserData[Load User-Specific Data]
    LoadUserData --> ProcessRequest[Process with User Context]
    
    ProcessRequest --> UserSpecific{User-Specific Logic}
    UserSpecific --> US1[User Risk Rules]
    UserSpecific --> US2[User Strategies]
    UserSpecific --> US3[User Preferences]
    
    US1 --> ExecuteAction[Execute Action]
    US2 --> ExecuteAction
    US3 --> ExecuteAction
    
    ExecuteAction --> UpdateUserState[Update User State]
    UpdateUserState --> LogUserAction[Log with User ID]
    LogUserAction --> ReturnResult[Return Result]
```

## User Directory Structure

```mermaid
graph TD
    RootDir[Trading System Root] --> UsersDir[users/]
    
    UsersDir --> User1Dir[user1/]
    UsersDir --> User2Dir[user2/]
    UsersDir --> UserNDir[userN/]
    
    User1Dir --> U1Config[config/]
    User1Dir --> U1Data[data/]
    User1Dir --> U1Logs[logs/]
    User1Dir --> U1State[state/]
    
    U1Config --> C1[user_config.ini]
    U1Config --> C2[strategies.json]
    U1Config --> C3[risk_params.json]
    
    U1Data --> D1[orders.xlsx]
    U1Data --> D2[positions.json]
    U1Data --> D3[performance.db]
    
    U1Logs --> L1[trading.log]
    U1Logs --> L2[errors.log]
    U1Logs --> L3[audit.log]
    
    U1State --> S1[trading_state.json]
    U1State --> S2[session.json]
    U1State --> S3[cache.db]
```

## Multi-User Service Architecture

```mermaid
sequenceDiagram
    participant MainApp
    participant UserManager
    participant User1Service
    participant User2Service
    participant SharedResource
    participant KiteAPI
    
    MainApp->>UserManager: Initialize system
    UserManager->>UserManager: Load all users
    UserManager->>User1Service: Start User1 services
    UserManager->>User2Service: Start User2 services
    
    User1Service->>SharedResource: Request resource
    SharedResource-->>User1Service: Allocate resource
    User1Service->>KiteAPI: User1 API call
    KiteAPI-->>User1Service: Response
    
    User2Service->>SharedResource: Request resource
    SharedResource-->>User2Service: Allocate resource
    User2Service->>KiteAPI: User2 API call
    KiteAPI-->>User2Service: Response
    
    User1Service->>UserManager: Update status
    User2Service->>UserManager: Update status
    
    UserManager->>MainApp: System status
```

## User Permission System

```mermaid
flowchart TD
    Permissions([User Permissions]) --> PermissionTypes[Permission Categories]
    
    PermissionTypes --> Trading[Trading Permissions]
    PermissionTypes --> Data[Data Access]
    PermissionTypes --> System[System Access]
    PermissionTypes --> Reports[Report Access]
    
    Trading --> T1[Can Trade]
    Trading --> T2[Max Order Size]
    Trading --> T3[Allowed Products]
    Trading --> T4[Allowed Segments]
    
    Data --> D1[View Own Data]
    Data --> D2[View All Data]
    Data --> D3[Export Data]
    Data --> D4[Delete Data]
    
    System --> S1[Change Settings]
    System --> S2[Add Strategies]
    System --> S3[System Admin]
    System --> S4[User Management]
    
    Reports --> R1[View Reports]
    Reports --> R2[Generate Reports]
    Reports --> R3[Share Reports]
    Reports --> R4[Customize Reports]
    
    CheckPermission([Check Permission]) --> LoadUserPerms[Load User Permissions]
    LoadUserPerms --> CheckSpecific{Has Permission?}
    CheckSpecific -->|Yes| AllowAction[Allow Action]
    CheckSpecific -->|No| DenyAction[Deny Action]
    
    DenyAction --> LogAttempt[Log Denied Attempt]
    AllowAction --> LogAccess[Log Allowed Access]
```

## User Context Cleanup

```mermaid
flowchart TD
    Cleanup([Context Cleanup]) --> TriggerCleanup{Cleanup Trigger}
    
    TriggerCleanup -->|Logout| LogoutCleanup[User Logout]
    TriggerCleanup -->|Timeout| TimeoutCleanup[Session Timeout]
    TriggerCleanup -->|Error| ErrorCleanup[Error Recovery]
    TriggerCleanup -->|Shutdown| ShutdownCleanup[System Shutdown]
    
    LogoutCleanup --> SaveState[Save User State]
    TimeoutCleanup --> SaveState
    ErrorCleanup --> SaveState
    ShutdownCleanup --> SaveAllStates[Save All User States]
    
    SaveState --> CloseConnections[Close User Connections]
    SaveAllStates --> CloseAllConnections[Close All Connections]
    
    CloseConnections --> ReleaseResources[Release Resources]
    CloseAllConnections --> ReleaseAllResources[Release All Resources]
    
    ReleaseResources --> ClearMemory[Clear User Memory]
    ReleaseAllResources --> ClearAllMemory[Clear All Memory]
    
    ClearMemory --> UpdateStatus[Update User Status]
    ClearAllMemory --> SystemCleanup[System Cleanup]
    
    UpdateStatus --> CleanupComplete[Cleanup Complete]
    SystemCleanup --> ShutdownComplete[Shutdown Complete]
```