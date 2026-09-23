class BudgetAllocator:
    def allocate(self, total_budget, flight_cost, num_nights):
        """Split budget across categories"""
        
        # Handle price with comma (e.g., "$2,320")
        if isinstance(flight_cost, str):
            flight_cost = flight_cost.replace('$', '').replace(',', '')
        
        flight_cost = float(flight_cost)
        remaining = total_budget - flight_cost
        
        if remaining < 0:
            return {'error': 'Flight cost exceeds budget'}
        
        allocation = {
            'total_budget': total_budget,
            'flights': flight_cost,
            'hotels': remaining * 0.40,
            'activities': remaining * 0.35,
            'meals': remaining * 0.15,
            'transport': remaining * 0.10,
            'max_hotel_per_night': (remaining * 0.40) / num_nights
        }
        
        return allocation

if __name__ == '__main__':
    allocator = BudgetAllocator()
    budget = allocator.allocate(5000, '$821', 5)
    for key, value in budget.items():
        print(f"{key}: ${value:.2f}" if isinstance(value, float) else f"{key}: {value}")