<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="budget-row">
        <div class="budget-label">
          <span>{{ t('restocking.budget') }}</span>
          <span class="budget-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</span>
        </div>
        <input
          type="range"
          class="budget-slider"
          min="0"
          :max="maxBudget"
          step="500"
          v-model.number="budget"
        />
        <div class="budget-range-labels">
          <span>{{ currencySymbol }}0</span>
          <span>{{ currencySymbol }}{{ maxBudget.toLocaleString() }}</span>
        </div>
      </div>
    </div>

    <div v-if="orderConfirmation" class="confirmation-banner">
      <strong>{{ t('restocking.orderPlaced', { orderNumber: orderConfirmation.order_number }) }}</strong>
      <span>{{ t('restocking.leadTime', { days: orderConfirmation.lead_time_days }) }}</span>
      <button class="dismiss-btn" @click="orderConfirmation = null">&times;</button>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.recommendedItems') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.selectedCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ selectedTotal.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ Math.max(budget - selectedTotal, 0).toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th></th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.currentDemand') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.suggestedQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.subtotal') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.sku">
                <td>
                  <input type="checkbox" v-model="selectedSkus" :value="rec.sku" />
                </td>
                <td>
                  <strong>{{ translateProductName(rec.name) }}</strong>
                  <div class="sku-sub">{{ rec.sku }} &middot; {{ translateWarehouse(rec.warehouse) }}</div>
                </td>
                <td>
                  <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                  <span v-if="rec.partial" class="badge partial-badge">{{ t('restocking.partial') }}</span>
                </td>
                <td>{{ rec.current_demand }}</td>
                <td><strong>{{ rec.forecasted_demand }}</strong></td>
                <td>{{ rec.suggested_quantity }}</td>
                <td>{{ currencySymbol }}{{ rec.unit_cost.toFixed(2) }}</td>
                <td><strong>{{ currencySymbol }}{{ rec.suggested_cost.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="place-order-row">
          <button
            class="place-order-btn"
            :disabled="selectedSkus.length === 0 || placingOrder"
            @click="placeOrder"
          >
            {{ placingOrder ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName, translateWarehouse } = useI18n()
    const { getCurrentFilters } = useFilters()

    const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

    // Budget range determined from typical restock order sizes in this
    // dataset (a handful of SKUs at a few hundred units each lands well
    // under $50K); chosen directly rather than asking, since this session
    // is running unattended.
    const maxBudget = 50000
    const budget = ref(15000)

    const loading = ref(true)
    const error = ref(null)
    const recommendations = ref([])
    const selectedSkus = ref([])
    const orderConfirmation = ref(null)
    const placingOrder = ref(false)

    let debounceTimer = null

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const summary = await api.getRestockRecommendations(budget.value, filters)
        recommendations.value = summary.recommendations
        // Default to every recommended item selected.
        selectedSkus.value = summary.recommendations.map(r => r.sku)
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, 300)
    })

    const selectedTotal = computed(() => {
      return recommendations.value
        .filter(r => selectedSkus.value.includes(r.sku))
        .reduce((sum, r) => sum + r.suggested_cost, 0)
    })

    const placeOrder = async () => {
      const items = recommendations.value
        .filter(r => selectedSkus.value.includes(r.sku))
        .map(r => ({ sku: r.sku, name: r.name, quantity: r.suggested_quantity, unit_cost: r.unit_cost }))

      if (items.length === 0) return

      try {
        placingOrder.value = true
        const order = await api.placeRestockOrder(budget.value, items)
        orderConfirmation.value = order
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to place restocking order: ' + err.message
      } finally {
        placingOrder.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      currencySymbol,
      maxBudget,
      budget,
      loading,
      error,
      recommendations,
      selectedSkus,
      selectedTotal,
      orderConfirmation,
      placingOrder,
      placeOrder,
      translateProductName,
      translateWarehouse
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.budget-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-weight: 600;
  color: #334155;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2563eb;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
}

.budget-range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #94a3b8;
}

.confirmation-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 0.875rem 1.25rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.875rem;
}

.dismiss-btn {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 1.25rem;
  color: #065f46;
  cursor: pointer;
  line-height: 1;
}

.sku-sub {
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.125rem;
}

.partial-badge {
  background: #fef3c7;
  color: #92400e;
  margin-left: 0.375rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.place-order-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #f1f5f9;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.75rem 1.75rem;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
</style>
