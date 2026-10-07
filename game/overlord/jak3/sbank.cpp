#include "sbank.h"

#include "common/util/Assert.h"

#include "game/overlord/jak3/overlord.h"

namespace jak3 {

constexpr int kNumBanks = 8;
SoundBankInfo* gBanks[kNumBanks];

SoundBankInfo gCommonBank;
SoundBankInfo gModeBank;
SoundBankInfo gLevel0Bank, gLevel0hBank;
SoundBankInfo gLevel1Bank, gLevel1hBank;
SoundBankInfo gLevel2Bank, gLevel2hBank;

void jak3_overlord_init_globals_sbank() {
  gBanks[0] = &gCommonBank;
  gBanks[1] = &gModeBank;
  gBanks[2] = &gLevel0Bank;
  gBanks[3] = &gLevel0hBank;
  gBanks[4] = &gLevel1Bank;
  gBanks[5] = &gLevel1hBank;
  gBanks[6] = &gLevel2Bank;
  gBanks[7] = &gLevel2hBank;
}

// added
void PrintBanks() {
  printf("Loaded Banks\n");
  for (int i = 0; i < kNumBanks; i++) {
    printf(" [%d] %s %s (%d/%d)\n", i, gBanks[i]->m_name1, gBanks[i]->m_name2, gBanks[i]->in_use,
           gBanks[i]->loaded);
  }
}

void InitBanks() {
  for (int i = 0; i < kNumBanks; i++) {
    auto* bank = gBanks[i];
    bank->in_use = 0;
    bank->snd_handle = nullptr;
    bank->loaded = false;
    bank->idx = i;
    bank->unk0 = 0;
  }

  strncpyz(gBanks[0]->m_name2, "common", 0x10);
  gBanks[0]->m_nSpuMemSize = 0xbbe40;
  gBanks[0]->m_nSpuMemLoc = 0x1d1c0;

  strncpyz(gBanks[1]->m_name2, "mode", 0x10);
  gBanks[1]->m_nSpuMemSize = 0x25400;
  gBanks[1]->m_nSpuMemLoc = 0xe0000;

  strncpyz(gBanks[2]->m_name2, "level0", 0x10);
  gBanks[2]->m_nSpuMemLoc = 0x105400;
  gBanks[2]->m_nSpuMemSize = 0x51400;

  strncpyz(gBanks[3]->m_name2, "level0h", 0x10);
  gBanks[3]->m_nSpuMemLoc = 0x12de00;
  gBanks[3]->m_nSpuMemSize = 0x28a00;

  strncpyz(gBanks[4]->m_name2, "level1", 0x10);
  gBanks[4]->m_nSpuMemSize = 0x51400;
  gBanks[4]->m_nSpuMemLoc = 0x156800;

  strncpyz(gBanks[5]->m_name2, "level1h", 0x10);
  gBanks[5]->m_nSpuMemSize = 0x28a00;
  gBanks[5]->m_nSpuMemLoc = 0x17f200;

  strncpyz(gBanks[6]->m_name2, "level2", 0x10);
  gBanks[6]->m_nSpuMemSize = 0x51400;
  gBanks[6]->m_nSpuMemLoc = 0x1a7c00;

  strncpyz(gBanks[7]->m_name2, "level2h", 0x10);
  gBanks[7]->m_nSpuMemSize = 0x28a00;
  gBanks[7]->m_nSpuMemLoc = 0x1d0600;
}

/*!
 * Pick the bank record for a sound bank about to load: common and mode banks have theirs, a full
 * bank (mode 4) takes an empty pair of level records, a half bank (modes 6 to 8: halfa, halfb,
 * halfc) one record of a pair. Returns the record, set to that mode, or nullptr when there is no
 * room (the bank isn't loaded).
 */
SoundBankInfo* AllocateBankName(const char* name, u32 mode) {
  SoundBankInfo* bank = nullptr;

  // handle common case
  if (memcmp(name, "common", 7) == 0 || memcmp(name, "commonj", 8) == 0) {
    if (!gBanks[0]->in_use) {
      bank = gBanks[0];
    }
  } else if (memcmp(name, "mode", 4) == 0) {
    if (!gBanks[1]->in_use) {
      bank = gBanks[1];
    }
  }

  if (mode == 4) {
    for (int bank_idx = 2; bank_idx < kNumBanks; bank_idx += 2) {
      if (!gBanks[bank_idx]->in_use && !gBanks[bank_idx + 1]->in_use) {
        bank = gBanks[bank_idx];
        bank->m_nSpuMemSize = 0x51400;
        break;
      }
    }
  } else if (mode >= 6 && mode <= 8) {
    // og:jak2-haven-city changed: the decompiled search only ever looked at the first pair of level
    // records (its record index never moved), so a half bank (halfa, halfb, halfc) whose partner of
    // the same mode was in another pair wasn't loaded when no pair was empty, and its sounds were
    // missing. As the original: the free record next to a loaded half bank of the same mode, else
    // a pair with both records free.
    int pair = -1;
    for (int i = 2; i < kNumBanks && pair < 0; i += 2) {
      if ((gBanks[i]->in_use && gBanks[i]->mode == mode) ||
          (gBanks[i + 1]->in_use && gBanks[i + 1]->mode == mode)) {
        pair = i;
      }
    }
    if (pair >= 0) {
      if (!gBanks[pair]->in_use) {
        bank = gBanks[pair];
      } else if (!gBanks[pair + 1]->in_use) {
        bank = gBanks[pair + 1];
      }
    } else {
      for (int i = 2; i < kNumBanks; i += 2) {
        if (!gBanks[i]->in_use && !gBanks[i + 1]->in_use) {
          bank = gBanks[i];
          break;
        }
      }
    }
    if (bank) {
      bank->m_nSpuMemSize = 0x28a00;
    }
  }

  if (bank) {
    bank->mode = mode;
    bank->snd_handle = nullptr;
    bank->unk0 = 0;
  }
  return bank;
}

/*!
 * The record of the loaded sound bank with this name, or nullptr.
 */
SoundBankInfo* LookupBank(const char* name) {
  for (int i = kNumBanks; i-- > 0;) {
    // og:jak2-haven-city changed: only a loaded record (in_use), as Jak 1 and 2's LookupBank. An
    // unloaded bank keeps its name in its record: found, it made the bank's next load be skipped
    // (its sounds missing until that record was reused).
    if (gBanks[i]->in_use && memcmp(name, gBanks[i]->m_name1, 16) == 0) {
      return gBanks[i];
    }
  }
  return nullptr;
}

int GetFalloffCurve(int x) {
  if (x < 0) {
    return 1;
  }
  if (x == 0 || 0x28 < x) {
    x = 2;
  }
  return x;
}
}  // namespace jak3