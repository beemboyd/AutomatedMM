# Migration Plan: Single-User to Multi-User Architecture

## Current Issues Identified

### 🚨 Critical Problems
1. **Singleton Conflicts**: All scripts share same instances regardless of user
2. **State File Conflicts**: Single `trading_state.json` shared across users  
3. **Credential Bleeding**: Wrong user's API credentials used in concurrent operations
4. **Cache Conflicts**: Shared data caches between users

### 📁 Files That Need Updates

#### High Priority (Have Singleton Issues)
- ✅ `place_orders_daily.py` - PARTIALLY FIXED (but brittle)
- ❌ `hourly_candle_watchdog.py` - VULNERABLE
- ❌ `update_cnc_stoploss.py` - VULNERABLE  
- ❌ `Pattern_Daily.py` - VULNERABLE

#### Core Modules (Need User Context)
- ❌ `state_manager.py` - Single state file for all users
- ❌ `order_manager.py` - Uses global state manager
- ❌ `data_handler.py` - Shared cache across users
- ✅ `config.py` - FIXED (environment variable priority)

## 🏗️ Recommended Architecture Options

### Option 1: User Context Manager (RECOMMENDED)
**Pros:**
- Clean separation of user instances
- No singleton clearing needed
- Thread-safe user switching
- Minimal changes to existing logic

**Implementation:**
```python
# Before (problematic)
state_manager = get_state_manager()  # Global singleton

# After (user-aware)
context_manager.set_current_user("Som", credentials)
state_manager = get_user_state_manager()  # User-specific instance
```

### Option 2: User-Specific Factories
**Pros:**
- Explicit user passing
- Clear ownership of instances

**Cons:**
- Requires changing all function signatures
- More invasive code changes

### Option 3: Service Locator Pattern
**Pros:**
- Dynamic service resolution
- Flexible configuration

**Cons:**
- More complex architecture
- Harder to debug

## 🔄 Migration Steps

### Phase 1: Core Infrastructure (Week 1)
1. **Create UserContextManager** - Central user instance management
2. **Create UserAwareStateManager** - Separate state files per user
3. **Update config.py** - ✅ DONE (environment priority)
4. **Create user-aware factory functions**

### Phase 2: Script Updates (Week 2)
1. **Update place_orders_daily.py** - Use UserContextManager
2. **Update hourly_candle_watchdog.py** - Add user context support
3. **Update update_cnc_stoploss.py** - Add user context support
4. **Test multi-user scenarios**

### Phase 3: State Migration (Week 3)
1. **Data migration script** - Split existing trading_state.json by user
2. **Backup current state files**
3. **Validate user-specific state files**

### Phase 4: Testing & Validation (Week 4)
1. **Unit tests for user context**
2. **Integration tests with multiple users**
3. **Performance testing**
4. **Production deployment**

## 🛠️ Implementation Examples

### Current Problematic Pattern:
```python
# hourly_candle_watchdog.py - VULNERABLE
from data_handler import get_data_handler

class CandleWatchdog:
    def __init__(self):
        self.data_handler = get_data_handler()  # Uses first user's credentials!
```

### Fixed Pattern:
```python
# hourly_candle_watchdog.py - FIXED
from user_context_manager import get_context_manager, get_user_data_handler

class CandleWatchdog:
    def __init__(self, user_name: str, credentials: UserCredentials):
        # Set user context first
        get_context_manager().set_current_user(user_name, credentials)
        # Now get user-specific instance
        self.data_handler = get_user_data_handler()  # Correct user's credentials!
```

## 📊 Directory Structure Changes

### Current Structure:
```
Daily/
├── data/
│   └── trading_state.json          # SHARED by all users ❌
├── logs/
│   ├── Sai/                       # User-specific ✅
│   └── Som/                       # User-specific ✅
└── Current_Orders/
    ├── Sai/                       # User-specific ✅
    └── Som/                       # User-specific ✅
```

### Proposed Structure:
```
Daily/
├── data/
│   ├── trading_state_Sai.json     # User-specific ✅
│   ├── trading_state_Som.json     # User-specific ✅
│   └── shared/                    # For non-user data
├── logs/
│   ├── Sai/                       # User-specific ✅
│   └── Som/                       # User-specific ✅
└── Current_Orders/
    ├── Sai/                       # User-specific ✅
    └── Som/                       # User-specific ✅
```

## 🎯 Expected Benefits

1. **True Multi-User Support**: Multiple users can run simultaneously
2. **Data Isolation**: No cross-contamination of user data
3. **Easier Debugging**: User-specific logs and state files
4. **Better Scalability**: Easy to add new users
5. **Reduced Bugs**: No more singleton-related credential mixing

## 🚀 Quick Win: Immediate Fix

For immediate relief, update these scripts with singleton clearing:

```python
# Add to ALL scripts that use singletons
def clear_all_singletons():
    import order_manager, state_manager, data_handler, config
    order_manager._order_manager = None
    state_manager._state_manager = None  
    data_handler._data_handler = None
    config._config = None

# Call before initializing services for a new user
clear_all_singletons()
```

But the UserContextManager approach is the proper long-term solution.