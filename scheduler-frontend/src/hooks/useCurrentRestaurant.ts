import { useEffect, useState } from 'react'
import { getRestaurants, type Restaurant } from '../api'

/** There's only ever one restaurant right now -- this just grabs the
 * first one. Once multi-restaurant selection matters, swap this for a
 * real picker backed by the same getRestaurants() call. */
export function useCurrentRestaurant() {
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRestaurants()
      .then((restaurants) => {
        if (restaurants.length === 0) {
          setError('No restaurants found.')
        } else {
          setRestaurant(restaurants[0])
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return { restaurant, loading, error }
}
